import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  bool _isLoading = false;
  bool _isAuthenticated = false;

  bool get isLoading => _isLoading;
  bool get isAuthenticated => _isAuthenticated;

  void setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners(); // Notify widgets to rebuild
  }

  void setAuthenticated(bool authenticated) {
    _isAuthenticated = authenticated;
    notifyListeners(); // Notify widgets to rebuild
  }

  // Add more functionality as needed
}
