"""AI card transport; callers handle failure and fall back to webhook delivery."""
import re
import uuid
import logging
import httpx
from app.config import get_settings


def visible(text: str) -> str:
    text = re.sub(r"[ \t]*\[cite:[^\]]*\]", "", text)
    return re.sub(r"\[(?:c(?:i(?:t(?:e(?::[^\]]*)?)?)?)?)?$", "", text)


class Card:
    def __init__(self, client, track, token):
        self.client, self.track = client, track
        self.headers = {"x-acs-dingtalk-access-token": token}
        self.started = False

    async def request(self, method, path, body):
        response = await self.client.request(method, "https://api.dingtalk.com/v1.0/" + path, headers=self.headers, json=body)
        if response.is_error:
            try:
                code = str(response.json().get("code", "unknown"))
            except ValueError:
                code = "non_json"
            logging.getLogger("xiaosu.im").warning("card_api_failed path=%s status=%s code=%s", path, response.status_code, re.sub(r"[^a-zA-Z0-9_.-]", "", code)[:160])
        response.raise_for_status()
        data = response.json()
        if data.get("success") is False or data.get("errcode", 0):
            raise RuntimeError("钉钉卡片请求失败")

    @classmethod
    async def create(cls, client, track, target):
        s = get_settings()
        response = await client.post("https://api.dingtalk.com/v1.0/oauth2/accessToken", json={"appKey": s.dingtalk_client_id, "appSecret": s.dingtalk_client_secret.get_secret_value()})
        response.raise_for_status()
        card = cls(client, track, response.json()["accessToken"])
        body = {"cardTemplateId": s.dingtalk_card_template_id, "outTrackId": track, "cardData": {"cardParamMap": {"flowStatus": "1", "content": "正在查询…"}}, "callbackType": "STREAM", "imGroupOpenSpaceModel": {"supportForward": False}, "imRobotOpenSpaceModel": {"supportForward": False}}
        if target["type"] == "2":
            body.update(openSpaceId="dtv1.card//IM_GROUP." + target["conversation"], imGroupOpenDeliverModel={"robotCode": s.dingtalk_client_id})
        elif target["type"] == "1" and target.get("user"):
            body.update(openSpaceId="dtv1.card//IM_ROBOT." + target["user"], imRobotOpenDeliverModel={"spaceType": "IM_ROBOT"})
        else:
            raise ValueError("缺少卡片接收者")
        await card.request("POST", "card/instances/createAndDeliver", body)
        return card

    async def update(self, text, final=False, failed=False):
        if not self.started and not final:
            await self.request("PUT", "card/instances", {"outTrackId": self.track, "cardData": {"cardParamMap": {"flowStatus": "2"}}, "cardUpdateOptions": {"updateCardDataByKey": True}})
            self.started = True
        await self.request("PUT", "card/streaming", {"outTrackId": self.track, "guid": str(uuid.uuid4()), "key": "content", "content": text, "isFull": True, "isFinalize": final, "isError": failed})
        if final:
            await self.request("PUT", "card/instances", {"outTrackId": self.track, "cardData": {"cardParamMap": {"flowStatus": "5" if failed else "3", "content": text}}, "cardUpdateOptions": {"updateCardDataByKey": True}})
