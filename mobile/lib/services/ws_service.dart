import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../utils/constants.dart';
import '../utils/log.dart';
import 'client_info.dart';

class WsService {
  WebSocketChannel? _channel;
  bool _connected = false;

  Function(Map<String, dynamic>)? onEvent;
  Function(bool)? onStatus;

  bool get isConnected => _connected;

  void connect(String jwtToken) {
    try {
      // предотвратить множественные параллельные подключения
      if (_channel != null) {
        try {
          _channel!.sink.close();
        } catch (_) {}
        _channel = null;
      }
      _connected = false;
      onStatus?.call(false);

      final uri = Uri.parse(kWebSocketUrl).replace(
        queryParameters: {
          'token': jwtToken,
          'platform': ClientInfo.platform,
          'os': ClientInfo.os,
          'device': ClientInfo.device,
        },
      );
      logDebug('WS: Connecting to $uri');
      _channel = WebSocketChannel.connect(uri);

      // WebSocketChannel.connect не даёт явного "onOpen", поэтому считаем соединение активным
      // сразу после создания канала (ошибки/закрытие обработаются ниже).
      _connected = true;
      onStatus?.call(true);

      _channel!.stream.listen(
        (message) {
          try {
            final data = jsonDecode(message as String) as Map<String, dynamic>;
            logDebug('WS: Received message: $data');
            onEvent?.call(data);
          } catch (e) {
            logDebug('WS message error: $e');
          }
        },
        onDone: () {
          logDebug('WS: Connection closed');
          _connected = false;
          onStatus?.call(false);
        },
        onError: (error) {
          logDebug('WS error: $error');
          _connected = false;
          onStatus?.call(false);
        },
      );
    } catch (e) {
      logDebug('WS connect error: $e');
      _connected = false;
      onStatus?.call(false);
    }
  }

  void disconnect() {
    _channel?.sink.close();
    _channel = null;
    _connected = false;
    onStatus?.call(false);
  }

  Future<bool> connectToTikTok(String username) async {
    if (_channel == null) {
      logDebug('WS not connected, cannot connect to TikTok');
      return false;
    }
    
    try {
      final message = jsonEncode({
        'action': 'connect_tiktok',
        'username': username,
      });
      _channel?.sink.add(message);
      logDebug('WS: Sent TikTok connect request for $username');
      return true;
    } catch (e) {
      logDebug('WS: Error sending TikTok connect request: $e');
      return false;
    }
  }

  Future<void> disconnectFromTikTok() async {
    if (_channel == null) {
      return;
    }
    
    try {
      final message = jsonEncode({
        'action': 'disconnect_tiktok',
      });
      _channel?.sink.add(message);
      logDebug('WS: Sent TikTok disconnect request');
    } catch (e) {
      logDebug('WS: Error sending TikTok disconnect request: $e');
    }
  }
}
