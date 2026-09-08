import 'package:flutter_test/flutter_test.dart';
import 'package:edith_app/main.dart';

void main() {
  testWidgets('EdithMobileApp smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const EdithMobileApp());
    expect(find.text('HUD'), findsWidgets);
  });
}
