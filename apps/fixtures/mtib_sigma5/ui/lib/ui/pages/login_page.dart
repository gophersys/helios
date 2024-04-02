import 'package:flutter/material.dart';
import '../../providers/app_state.dart';
import 'package:provider/provider.dart';

class LoginPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text('Login Page'),
            SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                // Here you should implement the login logic
                // For now, just navigate to the HomePage
                Navigator.of(context).pushReplacementNamed('/home');
              },
              child: Text('Login'),
            ),
          ],
        ),
      ),
    );
  }
}
