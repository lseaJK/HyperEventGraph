// src/services/websocket.ts

const WS_URL = 'ws://localhost:8080/ws/1'; // 使用client_id=1

let socket: WebSocket | null = null;
const reconnectDelay = 3000; // 重连延迟时间（毫秒）
let reconnectTimeout: number | null = null;

// 连接WebSocket并设置自动重连
export const connectWebSocket = (onMessage: (message: string) => void) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    console.log('WebSocket已连接');
    return;
  }
  
  // 清除可能存在的重连定时器
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }

  try {
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
      console.log('WebSocket连接已建立');
      onMessage('已连接到服务器日志流...');
    };

    socket.onmessage = (event) => {
      onMessage(event.data);
    };

    socket.onerror = (error) => {
      console.error('WebSocket错误:', error);
      onMessage(`WebSocket错误: [object Event]`);
    };

    socket.onclose = () => {
      console.log('WebSocket连接已关闭，尝试重新连接...');
      onMessage('与服务器日志流的连接已关闭，尝试重新连接...');
      socket = null;
      
      // 设置重连定时器
      reconnectTimeout = setTimeout(() => {
        connectWebSocket(onMessage);
      }, reconnectDelay);
    };
  } catch (error) {
    console.error('WebSocket连接失败:', error);
    onMessage(`WebSocket连接失败: ${error}`);
    
    // 连接失败也尝试重连
    reconnectTimeout = setTimeout(() => {
      connectWebSocket(onMessage);
    }, reconnectDelay);
  }
};

// 断开WebSocket连接
export const disconnectWebSocket = () => {
  // 清除重连定时器
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
  
  if (socket) {
    socket.close();
    socket = null;
  }
};
