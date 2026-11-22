import React from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import App from './App';
import './style.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode><ConfigProvider theme={{ token: { colorPrimary: '#285d59', borderRadius: 8 } }}><App /></ConfigProvider></React.StrictMode>,
);
