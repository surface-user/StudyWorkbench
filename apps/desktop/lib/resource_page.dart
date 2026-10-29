import 'package:flutter/material.dart';

import 'backend.dart';
import 'document_page.dart';
import 'media_page.dart';
import 'page_activity.dart';
import 'resource_explorer.dart';
import 'web_page.dart';
import 'workspace_layout.dart';

/// Resolve stable identity before handing content to an isolated viewer.
class ResourcePage extends StatefulWidget {
  const ResourcePage({
    required this.backend,
    required this.workspaceId,
    required this.tab,
    required this.onChanged,
    this.onActivity,
    super.key,
  });
  final Backend backend;
  final String workspaceId;
  final WorkbenchTab tab;
  final VoidCallback onChanged;
  final PageActivityChanged? onActivity;
  @override
  State<ResourcePage> createState() => _ResourcePageState();
}

class _ResourcePageState extends State<ResourcePage> {
  Map<String, dynamic>? node;
  String? error;
  bool loading = true;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    widget.onActivity?.call(loading: true);
    try {
      final value = Map<String, dynamic>.from(
        await widget.backend.request(
          'GET',
          '/api/workspaces/${widget.workspaceId}/nodes/${widget.tab.resourceItemId}',
        ) as Map,
      );
      if (!mounted) return;
      final view = switch (value['kind']) {
        'link' => 'web',
        'media' => 'media',
        _ => 'document',
      };
      if (view != widget.tab.viewKind || value['kind'] == 'folder') {
        throw const FormatException('资源类型与保存的标签不符，原始标签已保留');
      }
      if (widget.tab.resourceName != value['name']) {
        widget.tab.resourceName = value['name'] as String;
        widget.onChanged();
      }
      setState(() => node = value);
    } catch (failure) {
      if (mounted) setState(() => error = '资源无法打开（缺失或读取失败），标签与草稿已保留：$failure');
    } finally {
      if (mounted) {
        setState(() => loading = false);
        widget.onActivity?.call(loading: false, error: error);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    final value = node;
    if (error != null ||
        value == null ||
        (value['status'] != 'ready' && widget.tab.viewKind != 'document')) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SelectableText(error ?? resourceStatus(value?['status'])),
            TextButton(onPressed: load, child: const Text('重试打开资源')),
          ],
        ),
      );
    }
    final tab = widget.tab;
    late final profile =
        '${widget.backend.dataDir}/workspaces/${widget.workspaceId}/resource/${tab.id}';
    return switch (tab.viewKind) {
      'web' => WebPage(
        profile: profile,
        initialUrl: tab.url ?? value['url'] as String?,
        onActivity: widget.onActivity,
        onUrlChanged: (url) {
          if (tab.url != url) {
            tab.url = url;
            widget.onChanged();
          }
        },
      ),
      'media' => MediaPage(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        profile: profile,
        mediaId: value['media_id'] as String,
        onActivity: widget.onActivity,
      ),
      _ => DocumentPage(
        backend: widget.backend,
        workspaceId: widget.workspaceId,
        tab: tab,
        onChanged: widget.onChanged,
        onActivity: widget.onActivity,
      ),
    };
  }
}
