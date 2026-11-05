import 'package:flutter/material.dart';

class SpreadsheetView extends StatelessWidget {
  const SpreadsheetView({
    required this.workbook,
    required this.sheetIndex,
    required this.onSheetChanged,
    required this.scrollController,
    super.key,
  });

  final Map<String, dynamic> workbook;
  final int sheetIndex;
  final ValueChanged<int> onSheetChanged;
  final ScrollController scrollController;

  @override
  Widget build(BuildContext context) {
    final sheets = workbook['sheets'] as List;
    final selected = sheetIndex.clamp(0, sheets.length - 1);
    final cells = sheets[selected]['cells'] as List;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(
          padding: EdgeInsets.all(8),
          child: Text(
            'XLSX只读单元格列表 · 仅资料级书签\n公式只显示文件中的缓存值，可能过期；无缓存不会计算。数字/日期序列为原始值，不还原样式、合并布局或图表。',
          ),
        ),
        DropdownButton<int>(
          isExpanded: true,
          value: selected,
          items: [
            for (var i = 0; i < sheets.length; i++)
              DropdownMenuItem(
                value: i,
                child: Text(
                  '${i + 1}. ${sheets[i]['name']}${sheets[i]['state'] == 'visible' ? '' : '（隐藏表）'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged: (value) {
            if (value != null) onSheetChanged(value);
          },
        ),
        Expanded(
          child: cells.isEmpty
              ? const Center(child: Text('此表没有单元格值'))
              : ListView.builder(
                  key: ValueKey('xlsx-sheet-$selected'),
                  controller: scrollController,
                  itemCount: cells.length,
                  itemBuilder: (context, index) {
                    final cell = cells[index] as Map;
                    return Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            width: 110,
                            child: Text(cell['address'] as String),
                          ),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SelectableText(cell['value'] as String),
                                if (cell['formula'] == true)
                                  Text(
                                    cell['cache_missing'] == true
                                        ? '未计算'
                                        : '公式缓存（未重新计算）',
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelSmall,
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
