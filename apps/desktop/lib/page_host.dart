import 'package:flutter/material.dart';

/// Keep identity on the direct Stack child, including when siblings move/close.
class PageHost extends StatelessWidget {
  const PageHost({required this.activeId, required this.pages, super.key});
  final String? activeId;
  final Map<String, Widget> pages;

  @override
  Widget build(BuildContext context) => Stack(
    fit: StackFit.expand,
    children: [
      for (final entry in pages.entries)
        Offstage(
          key: ValueKey(entry.key),
          offstage: entry.key != activeId,
          child: TickerMode(
            enabled: entry.key == activeId,
            child: ExcludeFocus(
              excluding: entry.key != activeId,
              child: entry.value,
            ),
          ),
        ),
    ],
  );
}
