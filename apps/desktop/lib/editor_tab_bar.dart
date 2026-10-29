import 'dart:math' as math;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import 'workspace_layout.dart';

IconData tabIcon(String kind) => switch (kind) {
  'study' => Icons.school_outlined,
  'question' => Icons.quiz_outlined,
  'web' => Icons.language,
  'player' => Icons.play_circle_outline,
  'import' => Icons.library_books_outlined,
  'welcome' => Icons.home_outlined,
  _ => Icons.insert_drive_file_outlined,
};

class EditorTabBar extends StatefulWidget {
  const EditorTabBar({
    required this.layout,
    required this.onSelect,
    required this.onClose,
    required this.onNew,
    required this.onReopen,
    required this.onMove,
    required this.onMenu,
    required this.isDirty,
    this.enabled = true,
    super.key,
  });
  final WorkspaceLayout layout;
  final ValueChanged<String> onSelect, onClose, onNew;
  final VoidCallback onReopen;
  final void Function(String, String) onMove, onMenu;
  final bool Function(WorkbenchTab) isDirty;
  final bool enabled;

  @override
  State<EditorTabBar> createState() => _EditorTabBarState();
}

class _TabEntry {
  _TabEntry(this.tab);
  WorkbenchTab tab;
  bool closing = false;
  final key = GlobalKey();
}

class _EditorTabBarState extends State<EditorTabBar> {
  final scroll = ScrollController();
  final entries = <_TabEntry>[];
  String? active;
  String? activeTitle;
  double? viewport;

  @override
  void initState() {
    super.initState();
    entries.addAll(widget.layout.tabs.map(_TabEntry.new));
    active = widget.layout.activeId;
    activeTitle = entries
        .where((e) => e.tab.id == active)
        .firstOrNull
        ?.tab
        .title;
    _reveal();
  }

  @override
  void didUpdateWidget(covariant EditorTabBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    final old = [...entries];
    final byId = {for (final entry in old) entry.tab.id: entry};
    entries.clear();
    for (final tab in widget.layout.tabs) {
      final entry = byId.remove(tab.id) ?? _TabEntry(tab);
      entry.tab = tab;
      entry.closing = false;
      entries.add(entry);
    }
    for (final entry in byId.values) {
      entry.closing = true;
      entries.insert(math.min(old.indexOf(entry), entries.length), entry);
    }
    final nextTitle = entries
        .where((e) => e.tab.id == widget.layout.activeId)
        .firstOrNull
        ?.tab
        .title;
    if (activeTitle != nextTitle ||
        active != widget.layout.activeId ||
        old.map((e) => e.tab.id).join() !=
            entries.map((e) => e.tab.id).join()) {
      active = widget.layout.activeId;
      activeTitle = nextTitle;
      _reveal();
    }
  }

  bool get reduceMotion =>
      MediaQuery.disableAnimationsOf(context) ||
      MediaQuery.accessibleNavigationOf(context);

  void _reveal() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final entry = entries
          .where((e) => e.tab.id == active && !e.closing)
          .firstOrNull;
      final target = entry?.key.currentContext;
      if (target != null) {
        Scrollable.ensureVisible(
          target,
          alignment: 0.5,
          duration: Duration(milliseconds: reduceMotion ? 0 : 120),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  double _width(WorkbenchTab tab) {
    final text = TextPainter(
      text: TextSpan(text: tab.title, style: const TextStyle(fontSize: 13)),
      textDirection: Directionality.of(context),
      textScaler: MediaQuery.textScalerOf(context),
      maxLines: 1,
    )..layout();
    final width = (text.width + 76).clamp(112.0, 220.0);
    text.dispose();
    return width;
  }

  @override
  void dispose() {
    scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return ScrollConfiguration(
      behavior: ScrollConfiguration.of(context).copyWith(scrollbars: false),
      child: SizedBox(
        height: 38,
        child: Material(
          color: colors.surfaceContainerLow.withValues(alpha: 0.85),
          child: LayoutBuilder(
            builder: (context, constraints) {
              if (viewport != constraints.maxWidth) {
                viewport = constraints.maxWidth;
                _reveal();
              }
              final widths = {
                for (final entry in entries) entry.tab.id: _width(entry.tab),
              };
              final total = widths.values.fold(0.0, (a, b) => a + b);
              final available = math.max(0.0, constraints.maxWidth - 96);
              return Row(
                children: [
                  SizedBox(
                    width: math.min(total, available),
                    child: Listener(
                      onPointerSignal: (event) {
                        if (event is PointerScrollEvent && scroll.hasClients) {
                          GestureBinding.instance.pointerSignalResolver
                              .register(event, (_) {
                                scroll.jumpTo(
                                  (scroll.offset +
                                          event.scrollDelta.dy +
                                          event.scrollDelta.dx)
                                      .clamp(
                                        0.0,
                                        scroll.position.maxScrollExtent,
                                      ),
                                );
                              });
                        }
                      },
                      child: SingleChildScrollView(
                        key: const ValueKey('editor-tab-scroll'),
                        controller: scroll,
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            for (final entry in entries)
                              _TabAppearance(
                                key: ValueKey(entry.tab.id),
                                closing: entry.closing,
                                reduced: reduceMotion,
                                onOpened: entry.tab.id == active
                                    ? _reveal
                                    : () {},
                                onRemoved: () {
                                  WidgetsBinding.instance.addPostFrameCallback((
                                    _,
                                  ) {
                                    if (mounted && entry.closing) {
                                      setState(() => entries.remove(entry));
                                    }
                                  });
                                },
                                child: SizedBox(
                                  key: entry.key,
                                  width: widths[entry.tab.id],
                                  height: 38,
                                  child: _EditorTabItem(
                                    tab: entry.tab,
                                    active: entry.tab.id == active,
                                    dirty: widget.isDirty(entry.tab),
                                    reduced: reduceMotion,
                                    enabled: widget.enabled && !entry.closing,
                                    onSelect: () =>
                                        widget.onSelect(entry.tab.id),
                                    onClose: () => widget.onClose(entry.tab.id),
                                    onMove: (id) =>
                                        widget.onMove(id, entry.tab.id),
                                    onMenu: (action) =>
                                        widget.onMenu(entry.tab.id, action),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  PopupMenuButton<String>(
                    tooltip: '新建标签页',
                    enabled: widget.enabled && widget.layout.tabs.length < 16,
                    icon: const Icon(Icons.add, size: 18),
                    style: _toolStyle,
                    onSelected: widget.onNew,
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'welcome', child: Text('欢迎 / 添加资源')),
                      PopupMenuItem(value: 'study', child: Text('题库与学习计划')),
                      PopupMenuItem(value: 'question', child: Text('富内容题目')),
                      PopupMenuItem(value: 'web', child: Text('网页')),
                      PopupMenuItem(value: 'import', child: Text('导入与资料库')),
                      PopupMenuItem(value: 'player', child: Text('本地播放器')),
                    ],
                  ),
                  IconButton(
                    tooltip: '重新打开关闭的标签页',
                    style: _toolStyle,
                    onPressed: widget.enabled && widget.layout.closed.isNotEmpty
                        ? widget.onReopen
                        : null,
                    icon: const Icon(Icons.restore_page_outlined, size: 16),
                  ),
                  PopupMenuButton<String>(
                    tooltip: '标签列表与更多操作',
                    style: _toolStyle,
                    icon: const Icon(Icons.more_horiz, size: 18),
                    onSelected: (id) => id == 'close-all'
                        ? widget.onMenu('', 'all')
                        : widget.onSelect(id),
                    itemBuilder: (_) => [
                      for (final tab in widget.layout.tabs)
                        PopupMenuItem(
                          value: tab.id,
                          child: Row(
                            children: [
                              Icon(
                                tab.id == active
                                    ? Icons.check
                                    : tabIcon(tab.kind),
                                size: 16,
                              ),
                              const SizedBox(width: 8),
                              Flexible(
                                child: Text(
                                  tab.title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      if (widget.layout.tabs.isNotEmpty) ...[
                        const PopupMenuDivider(),
                        const PopupMenuItem(
                          value: 'close-all',
                          child: Text('关闭全部标签'),
                        ),
                      ],
                    ],
                  ),
                  Expanded(
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onDoubleTap: widget.enabled
                          ? () => widget.onNew('welcome')
                          : null,
                      child: const SizedBox.expand(),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

final _toolStyle = IconButton.styleFrom(
  minimumSize: const Size(32, 32),
  maximumSize: const Size(32, 38),
  padding: EdgeInsets.zero,
  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
);

class _TabAppearance extends StatelessWidget {
  const _TabAppearance({
    required this.closing,
    required this.reduced,
    required this.onRemoved,
    required this.onOpened,
    required this.child,
    super.key,
  });
  final bool closing, reduced;
  final VoidCallback onRemoved, onOpened;
  final Widget child;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(begin: 0, end: closing ? 0 : 1),
    duration: Duration(
      milliseconds: reduced
          ? 0
          : closing
          ? 140
          : 160,
    ),
    curve: Curves.easeOutCubic,
    onEnd: closing ? onRemoved : onOpened,
    child: child,
    builder: (_, value, child) => ClipRect(
      child: Align(
        alignment: Alignment.centerLeft,
        widthFactor: value,
        child: Opacity(opacity: value, child: child),
      ),
    ),
  );
}

class _EditorTabItem extends StatefulWidget {
  const _EditorTabItem({
    required this.tab,
    required this.active,
    required this.dirty,
    required this.reduced,
    required this.enabled,
    required this.onSelect,
    required this.onClose,
    required this.onMove,
    required this.onMenu,
  });
  final WorkbenchTab tab;
  final bool active, dirty, reduced, enabled;
  final VoidCallback onSelect, onClose;
  final ValueChanged<String> onMove, onMenu;
  @override
  State<_EditorTabItem> createState() => _EditorTabItemState();
}

class _EditorTabItemState extends State<_EditorTabItem> {
  bool hover = false, focus = false;
  final focusNode = FocusNode();
  @override
  void dispose() {
    focusNode.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant _EditorTabItem oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!oldWidget.active && widget.active) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) focusNode.requestFocus();
      });
    }
  }

  Future<void> menu(Offset position) async {
    final tab = widget.tab;
    final overlay =
        Overlay.of(context).context.findRenderObject()! as RenderBox;
    final result = await showMenu<String>(
      context: context,
      position: RelativeRect.fromRect(
        position & Size.zero,
        Offset.zero & overlay.size,
      ),
      items: [
        const PopupMenuItem(value: 'close', child: Text('关闭')),
        const PopupMenuItem(value: 'others', child: Text('关闭其他标签')),
        const PopupMenuItem(value: 'right', child: Text('关闭右侧标签')),
        const PopupMenuItem(value: 'all', child: Text('关闭全部标签')),
        if ((tab.kind == 'web' || tab.viewKind == 'web') && tab.url != null)
          const PopupMenuItem(value: 'copy', child: Text('复制页面地址')),
      ],
    );
    if (mounted && result != null) widget.onMenu(result);
  }

  @override
  Widget build(BuildContext context) {
    final tab = widget.tab;
    final colors = Theme.of(context).colorScheme;
    final foreground = widget.active
        ? colors.onSurface
        : colors.onSurfaceVariant;
    final label =
        '${tab.title}${tab.loading ? ' · 正在加载' : ''}${tab.error != null ? ' · 加载失败：${tab.error}' : ''}${widget.dirty ? ' · 未保存' : ''}';
    final content = MouseRegion(
      onEnter: (_) => setState(() => hover = true),
      onExit: (_) => setState(() => hover = false),
      child: Semantics(
        selected: widget.active,
        label: label,
        child: Tooltip(
          message: label,
          child: GestureDetector(
            onSecondaryTapDown: widget.enabled
                ? (event) => menu(event.globalPosition)
                : null,
            child: AnimatedContainer(
              duration: Duration(milliseconds: widget.reduced ? 0 : 120),
              curve: Curves.easeOutCubic,
              decoration: BoxDecoration(
                color: widget.active
                    ? colors.surface
                    : hover
                    ? colors.surfaceContainerHighest
                    : Colors.transparent,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(5),
                ),
                border: Border.all(
                  color: colors.outlineVariant.withValues(alpha: 0.25),
                ),
              ),
              child: InkWell(
                key: ValueKey('select-tab-${tab.id}'),
                focusNode: focusNode,
                onFocusChange: (value) => setState(() => focus = value),
                onTap: widget.enabled
                    ? () {
                        focusNode.requestFocus();
                        widget.onSelect();
                      }
                    : null,
                child: Container(
                  foregroundDecoration: BoxDecoration(
                    border: focus
                        ? Border.all(color: colors.primary, width: 1.5)
                        : Border(
                            top: BorderSide(
                              color: widget.active
                                  ? colors.primary
                                  : Colors.transparent,
                              width: 2,
                            ),
                          ),
                  ),
                  padding: const EdgeInsets.only(left: 10, right: 4),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: tab.loading
                            ? CircularProgressIndicator(
                                strokeWidth: 1.5,
                                color: foreground,
                              )
                            : Icon(
                                tab.error != null
                                    ? Icons.error_outline
                                    : tabIcon(tab.kind),
                                size: 16,
                                color: tab.error != null
                                    ? colors.error
                                    : foreground,
                              ),
                      ),
                      const SizedBox(width: 7),
                      Expanded(
                        child: Text(
                          tab.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 13, color: foreground),
                        ),
                      ),
                      SizedBox(
                        width: 10,
                        child: widget.dirty
                            ? Icon(Icons.circle, size: 6, color: colors.primary)
                            : null,
                      ),
                      Opacity(
                        opacity: widget.active || hover || focus ? 1 : 0,
                        child: IconButton(
                          key: ValueKey('close-tab-${tab.id}'),
                          tooltip: '关闭${tab.title}',
                          onPressed: widget.enabled ? widget.onClose : null,
                          style: IconButton.styleFrom(
                            minimumSize: const Size(24, 24),
                            maximumSize: const Size(24, 24),
                            padding: EdgeInsets.zero,
                            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          ),
                          icon: Icon(Icons.close, size: 14, color: foreground),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    return DragTarget<String>(
      onWillAcceptWithDetails: (details) =>
          widget.enabled && details.data != tab.id,
      onAcceptWithDetails: (details) => widget.onMove(details.data),
      builder: (_, candidates, _) => DecoratedBox(
        decoration: BoxDecoration(
          border: candidates.isEmpty
              ? null
              : Border(left: BorderSide(color: colors.primary, width: 2)),
        ),
        child: Draggable<String>(
          data: tab.id,
          maxSimultaneousDrags: widget.enabled ? 1 : 0,
          feedback: Material(
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Text(tab.title),
            ),
          ),
          childWhenDragging: Opacity(opacity: 0.4, child: content),
          child: content,
        ),
      ),
    );
  }
}
