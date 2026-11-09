"""Pure merge core regression tests; also runnable without third-party packages."""

import itertools
import unittest

from study_workbench.markdown_merge import TEXT_LIMIT, MergePreview, preview_merge


class MarkdownMergeTests(unittest.TestCase):
    def assert_merge(self, base, local, current, expected):
        result = MergePreview(expected, expected is None)
        self.assertEqual(preview_merge(base, local, current), result)
        self.assertEqual(preview_merge(base, current, local), result)

    def test_identity_and_one_sided_changes(self):
        values = ['', 'a', 'a\n', '\n', '甲\r\n乙\n', 'x\u2028y', '<<<<<<< literal\n']
        for base, changed in itertools.product(values, repeat=2):
            with self.subTest(base=base, changed=changed):
                self.assert_merge(base, base, changed, changed)
                self.assert_merge(base, changed, changed, changed)

    def test_disjoint_replacements(self):
        self.assert_merge('a\nb\nc\n', 'A\nb\nc\n', 'a\nb\nC\n', 'A\nb\nC\n')
        self.assert_merge('a\nb\n', 'A\nb\n', 'a\nB\n', 'A\nB\n')

    def test_disjoint_insertions_and_deletions(self):
        self.assert_merge('a\nb\nc\n', 'x\na\nb\nc\n', 'a\nb\nc\ny\n', 'x\na\nb\nc\ny\n')
        self.assert_merge('a\nb\nc\n', 'b\nc\n', 'a\nb\n', 'b\n')
        self.assert_merge('a\nb\nc\n', 'x\na\nb\nc\n', 'a\nb\n', 'x\na\nb\n')

    def test_line_endings_and_literal_markdown_preserved(self):
        self.assert_merge('a\r\nb\r\nc', '甲\r\nb\r\nc', 'a\r\nb\r\n```', '甲\r\nb\r\n```')
        self.assert_merge('a\nb\nc\n', 'a\u2028z\nb\nc\n', 'a\nb\nC\n', 'a\u2028z\nb\nC\n')
        self.assert_merge('a\nb\nc\n', '<<<<<<< local\nb\nc\n', 'a\nb\nc', '<<<<<<< local\nb\nc')

    def test_conflicts_do_not_emit_candidate_or_markers(self):
        cases = [
            ('', 'a', 'b'),
            ('a\n', 'A\n', 'B\n'),
            ('a\nb\n', 'b\n', 'A\nb\n'),
            ('a\nb\n', 'x\na\nb\n', 'y\na\nb\n'),
            ('a\nb\n', 'x\na\nb\n', 'A\nb\n'),
            ('a\nb\n', 'a\nx\nb\n', 'A\nb\n'),
            ('a\nb\nc\n', 'A\nb\nC\n', 'a\nB\nc\n'),
            ('a\na\n', 'a\n', 'a\nb\n'),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assert_merge(*case, None)

    def test_exhaustive_distinct_line_replacements(self):
        original = [f'{i}\n' for i in range(6)]
        for left_start, left_end, right_start, right_end in itertools.product(range(7), repeat=4):
            if not (left_start < left_end <= right_start < right_end):
                continue
            local, current, expected = original.copy(), original.copy(), original.copy()
            local[left_start:left_end] = ['LOCAL\n']
            current[right_start:right_end] = ['CURRENT\n']
            expected[right_start:right_end] = ['CURRENT\n']
            expected[left_start:left_end] = ['LOCAL\n']
            self.assert_merge(''.join(original), ''.join(local), ''.join(current), ''.join(expected))

    def test_budget_and_utf8_validation_before_shortcuts(self):
        for bad in ['x' * (TEXT_LIMIT + 1), '甲' * (TEXT_LIMIT // 3 + 1), '\ud800', None, b'bytes']:
            for values in [(bad, '', ''), ('', bad, ''), ('', '', bad), (bad, bad, bad)]:
                with self.subTest(kind=type(bad), position=values.index(bad)):
                    with self.assertRaises(ValueError):
                        preview_merge(*values)
        self.assert_merge('', 'x' * TEXT_LIMIT, '', 'x' * TEXT_LIMIT)

    def test_merged_result_budget(self):
        base = 'a\nb\nc\n'
        half = 'x' * (TEXT_LIMIT // 2)
        with self.assertRaises(ValueError):
            preview_merge(base, half + '\nb\nc\n', 'a\nb\n' + half)


if __name__ == '__main__':
    unittest.main()
