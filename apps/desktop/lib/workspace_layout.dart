import 'dart:math';

class WorkbenchTab {
  WorkbenchTab({
    required this.id,
    required this.kind,
    this.url,
    this.draft = '',
    this.resourceItemId,
    this.viewKind,
    this.resourceName,
    this.opaque,
    this.draftBaseSha256,
    this.questionDraft = '',
    Map<String, dynamic>? documentState,
  }) : documentState = {
         'version': 1,
         'page': 1,
         'zoom': 1.0,
         'scroll': 0.0,
         'mode': 'read',
         'representation': 'original',
         ...?documentState,
       };
  factory WorkbenchTab.fromJson(Map<String, dynamic> value) {
    if (!const {
      'question',
      'web',
      'player',
      'import',
      'study',
      'resource',
      'welcome',
    }.contains(value['kind'])) {
      return WorkbenchTab(
        id: value['id'] as String,
        kind: value['kind'] as String,
        opaque: Map<String, dynamic>.from(value),
      );
    }
    return WorkbenchTab(
      id: value['id'] as String,
      kind: value['kind'] as String,
      url: value['url'] as String?,
      draft: value['draft'] as String? ?? '',
      resourceItemId: value['resource_item_id'] as String?,
      viewKind: value['view_kind'] as String?,
      resourceName: value['resource_name'] as String?,
      draftBaseSha256: value['draft_base_sha256'] as String?,
      questionDraft: value['question_draft'] as String? ?? '',
      documentState: value['document_state'] == null
          ? null
          : Map<String, dynamic>.from(value['document_state'] as Map),
    );
  }
  final String id;
  final String kind;
  String? url;
  String draft;
  final String? resourceItemId, viewKind;
  String? resourceName;
  final Map<String, dynamic>? opaque;
  String? draftBaseSha256;
  String questionDraft;
  Map<String, dynamic> Function()? captureView;
  Map<String, dynamic>? pendingView;
  // Transient verified navigation; the bookmark itself is persisted by the backend.
  Map<String, dynamic>? pendingAnchor;
  final Map<String, dynamic> documentState;
  // Runtime page status is deliberately excluded from the persisted layout.
  String? pageTitle;
  bool loading = false;
  String? error;
  String get title =>
      pageTitle ??
      switch (kind) {
        'question' => '富内容题目',
        'web' => url == null ? '网页' : Uri.parse(url!).host,
        'player' => '本地播放器',
        'import' => '导入与资料库',
        'study' => '题库与学习计划',
        'welcome' => '欢迎',
        'resource' => resourceName ?? '学习资源',
        _ => '不支持的标签页',
      };
  Map<String, dynamic> toJson() =>
      opaque ??
      {
        'id': id,
        'kind': kind,
        if (url != null) 'url': url,
        'draft': draft,
        if (resourceItemId != null) 'resource_item_id': resourceItemId,
        if (viewKind != null) 'view_kind': viewKind,
        if (resourceName != null) 'resource_name': resourceName,
        if (draftBaseSha256 != null) 'draft_base_sha256': draftBaseSha256,
        if (viewKind == 'document') 'document_state': documentState,
        if (questionDraft.isNotEmpty) 'question_draft': questionDraft,
      };
}

class WorkspaceLayout {
  WorkspaceLayout.fromJson(Map<String, dynamic> value)
    : version = value['version'] as int? ?? 1,
      tabs = (value['tabs'] as List)
          .map((v) => WorkbenchTab.fromJson(v))
          .toList(),
      closed = (value['closed_tabs'] as List)
          .map((v) => WorkbenchTab.fromJson(v))
          .toList(),
      activeId = value['active_tab_id'] as String?;
  final List<WorkbenchTab> tabs;
  final List<WorkbenchTab> closed;
  String? activeId;
  int version;

  void add(String kind) {
    if (tabs.length >= 16) throw StateError('每个工作空间最多打开 16 个标签页');
    final random = Random.secure();
    final id = List.generate(
      16,
      (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
    ).join();
    tabs.add(WorkbenchTab(id: id, kind: kind));
    if (kind == 'welcome') version = 2;
    activeId = id;
  }

  void openResource(Map<String, dynamic> node) {
    final id = node['resource_item_id'] as String;
    final view = switch (node['kind']) {
      'link' => 'web',
      'media' => 'media',
      _ => 'document',
    };
    final existing = tabs
        .where((t) => t.resourceItemId == id && t.viewKind == view)
        .firstOrNull;
    if (existing != null) {
      existing.pendingView = null;
      existing.resourceName = node['name'] as String;
      existing.pendingAnchor = node['learning_anchor'] == null
          ? null
          : Map<String, dynamic>.from(node['learning_anchor'] as Map);
      if (node['open_in_edit'] == true) existing.documentState['mode'] = 'edit';
      activeId = existing.id;
      return;
    }
    final recent = closed.lastIndexWhere(
      (t) => t.resourceItemId == id && t.viewKind == view,
    );
    if (recent >= 0) {
      if (tabs.length >= 16) throw StateError('请先关闭一个标签页');
      final tab = closed.removeAt(recent);
      tab.pendingView = null;
      tab.resourceName = node['name'] as String;
      tab.pendingAnchor = node['learning_anchor'] == null
          ? null
          : Map<String, dynamic>.from(node['learning_anchor'] as Map);
      if (node['open_in_edit'] == true) tab.documentState['mode'] = 'edit';
      tabs.add(tab);
      activeId = tab.id;
      version = 2;
      return;
    }
    add('resource');
    final tab = tabs.removeLast();
    tabs.add(
      WorkbenchTab(
        id: tab.id,
        kind: 'resource',
        resourceItemId: id,
        viewKind: view,
        resourceName: node['name'] as String,
        documentState: node['open_in_edit'] == true ? {'mode': 'edit'} : null,
      ),
    );
    tabs.last.pendingAnchor = node['learning_anchor'] == null
        ? null
        : Map<String, dynamic>.from(node['learning_anchor'] as Map);
    version = 2;
  }

  void close(String id) {
    final index = tabs.indexWhere((tab) => tab.id == id);
    if (index < 0) return;
    closed.add(tabs.removeAt(index));
    if (closed.length > 10) closed.removeAt(0);
    if (activeId == id) {
      activeId = tabs.isEmpty ? null : tabs[max(0, index - 1)].id;
    }
  }

  void openSingleton(String kind) {
    final existing = tabs.where((tab) => tab.kind == kind).firstOrNull;
    if (existing == null) {
      add(kind);
    } else {
      activeId = existing.id;
    }
  }

  void reopen() {
    if (closed.isEmpty) return;
    final recent = closed.last;
    final existing = recent.resourceItemId == null
        ? null
        : tabs
              .where(
                (t) =>
                    t.resourceItemId == recent.resourceItemId &&
                    t.viewKind == recent.viewKind,
              )
              .firstOrNull;
    if (existing != null) {
      activeId = existing.id;
      return;
    }
    if (tabs.length >= 16) throw StateError('请先关闭一个标签页');
    final tab = closed.removeLast();
    tabs.add(tab);
    activeId = tab.id;
  }

  void cycle(int direction) {
    if (tabs.isEmpty) return;
    final index = tabs.indexWhere((tab) => tab.id == activeId);
    activeId = tabs[(index + direction) % tabs.length].id;
  }

  void reorder(String dragged, String destination) {
    final from = tabs.indexWhere((tab) => tab.id == dragged);
    final to = tabs.indexWhere((tab) => tab.id == destination);
    if (from < 0 || to < 0 || from == to) return;
    tabs.insert(to, tabs.removeAt(from));
  }

  Map<String, dynamic> toJson() => {
    'version': version,
    'tabs': tabs.map((tab) => tab.toJson()).toList(),
    'closed_tabs': closed.map((tab) => tab.toJson()).toList(),
    'active_tab_id': activeId,
  };
}
