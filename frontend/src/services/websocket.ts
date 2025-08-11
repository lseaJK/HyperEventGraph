// src/services/websocket.ts

const WS_URL = 'ws://localhost:8000/ws/logs';

let socket: WebSocket | null = null;

export const connectWebSocket = (onMessage: (message: string) => void) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    console.log('WebSocket is already connected.');
    return;
  }

  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log('WebSocket connection established.');
    onMessage('Connection established with server log stream.');
  };

  socket.onmessage = (event) => {
    onMessage(event.data);
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
    onMessage('WebSocket error. Check console for details.');
  };

  socket.onclose = () => {
    console.log('WebSocket connection closed.');
    onMessage('Connection with server log stream closed.');
    socket = null;
  };
};

export const disconnectWebSocket = () => {
  if (socket) {
    socket.close();
  }
};
