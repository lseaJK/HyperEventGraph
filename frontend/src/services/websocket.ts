// src/services/websocket.ts

// 动态构建WebSocket URL，适配服务器端口映射
const getWebSocketURL = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname;
  
  // 如果是开发环境且访问localhost，使用8080端口
  // 否则使用当前页面的端口（适配服务器端口映射）
  let port = window.location.port;
  if (host === 'localhost' || host === '127.0.0.1') {
    port = '8080';
  }
  
  const wsUrl = `${protocol}//${host}:${port}/ws/1`;
  console.log('WebSocket URL:', wsUrl);
  return wsUrl;
};

let socket: WebSocket | null = null;
const reconnectDelay = 3000; // 重连延迟时间（毫秒）
let reconnectTimeout: number | null = null;

// 连接WebSocket并设置自动重连
export const connectWebSocket = (onMessage: (message: string) => void) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    return;
  }
  
  // 清除可能存在的重连定时器
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }

  try {
    const wsUrl = getWebSocketURL();
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      onMessage('已连接到服务器日志流...');
    };

    socket.onmessage = (event) => {
      onMessage(event.data);
    };

    socket.onerror = (error) => {
      console.error('WebSocket错误:', error);
      // 提供更友好的错误信息，不要直接显示[object Event]
      onMessage(`WebSocket连接出错，请检查后端服务是否启动`);
    };

    socket.onclose = () => {
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
