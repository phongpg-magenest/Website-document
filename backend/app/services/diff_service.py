"""
Diff Service - So sánh nội dung giữa hai phiên bản document
"""
import difflib
from typing import List, Tuple, Optional
from uuid import UUID

from app.schemas.document import DiffLine, DiffHunk, VersionCompareResponse


class DiffService:
    """Service for computing text differences between document versions"""

    def compute_diff(
        self,
        old_text: str,
        new_text: str,
        document_id: UUID,
        version_old: str,
        version_new: str,
        version_old_id: UUID,
        version_new_id: UUID,
        context_lines: int = 3
    ) -> VersionCompareResponse:
        """
        Compute unified diff between two text versions.

        Args:
            old_text: Content of older version
            new_text: Content of newer version
            document_id: UUID of the document
            version_old: Version string of older version
            version_new: Version string of newer version
            version_old_id: UUID of older version
            version_new_id: UUID of newer version
            context_lines: Number of context lines around changes

        Returns:
            VersionCompareResponse with diff details
        """
        # Handle None values
        old_text = old_text or ""
        new_text = new_text or ""

        # Split into lines
        old_lines = old_text.splitlines(keepends=False)
        new_lines = new_text.splitlines(keepends=False)

        # Use SequenceMatcher for similarity
        matcher = difflib.SequenceMatcher(None, old_text, new_text)
        similarity = matcher.ratio() * 100

        # Compute unified diff
        diff_generator = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"v{version_old}",
            tofile=f"v{version_new}",
            lineterm="",
            n=context_lines
        )

        # Parse diff output into hunks
        diff_hunks = self._parse_unified_diff(list(diff_generator))

        # Count additions and deletions
        total_additions = 0
        total_deletions = 0
        for hunk in diff_hunks:
            for line in hunk.lines:
                if line.change_type == "added":
                    total_additions += 1
                elif line.change_type == "removed":
                    total_deletions += 1

        return VersionCompareResponse(
            document_id=document_id,
            version_old=version_old,
            version_new=version_new,
            version_old_id=version_old_id,
            version_new_id=version_new_id,
            total_additions=total_additions,
            total_deletions=total_deletions,
            total_changes=total_additions + total_deletions,
            diff_hunks=diff_hunks,
            old_line_count=len(old_lines),
            new_line_count=len(new_lines),
            similarity_percentage=round(similarity, 2)
        )

    def _parse_unified_diff(self, diff_lines: List[str]) -> List[DiffHunk]:
        """
        Parse unified diff output into structured DiffHunk objects.

        Args:
            diff_lines: Lines from unified_diff output

        Returns:
            List of DiffHunk objects
        """
        hunks = []
        current_hunk = None
        old_line_num = 0
        new_line_num = 0

        for line in diff_lines:
            # Skip file headers
            if line.startswith("---") or line.startswith("+++"):
                continue

            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            if line.startswith("@@"):
                if current_hunk:
                    hunks.append(current_hunk)

                # Parse the @@ -1,5 +1,6 @@ format
                try:
                    parts = line.split()
                    old_range = parts[1][1:]  # Remove the "-"
                    new_range = parts[2][1:]  # Remove the "+"

                    if "," in old_range:
                        old_start, old_count = map(int, old_range.split(","))
                    else:
                        old_start, old_count = int(old_range), 1

                    if "," in new_range:
                        new_start, new_count = map(int, new_range.split(","))
                    else:
                        new_start, new_count = int(new_range), 1

                    current_hunk = DiffHunk(
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=[]
                    )
                    old_line_num = old_start
                    new_line_num = new_start
                except (ValueError, IndexError):
                    continue
                continue

            if current_hunk is None:
                continue

            # Parse diff lines
            if line.startswith("-"):
                current_hunk.lines.append(DiffLine(
                    line_number_old=old_line_num,
                    line_number_new=None,
                    content=line[1:],
                    change_type="removed"
                ))
                old_line_num += 1
            elif line.startswith("+"):
                current_hunk.lines.append(DiffLine(
                    line_number_old=None,
                    line_number_new=new_line_num,
                    content=line[1:],
                    change_type="added"
                ))
                new_line_num += 1
            elif line.startswith(" "):
                current_hunk.lines.append(DiffLine(
                    line_number_old=old_line_num,
                    line_number_new=new_line_num,
                    content=line[1:],
                    change_type="unchanged"
                ))
                old_line_num += 1
                new_line_num += 1
            else:
                # Handle lines that don't start with space (shouldn't happen normally)
                current_hunk.lines.append(DiffLine(
                    line_number_old=old_line_num,
                    line_number_new=new_line_num,
                    content=line,
                    change_type="unchanged"
                ))
                old_line_num += 1
                new_line_num += 1

        # Don't forget the last hunk
        if current_hunk:
            hunks.append(current_hunk)

        return hunks

    def get_inline_diff(
        self,
        old_text: str,
        new_text: str
    ) -> List[Tuple[str, str]]:
        """
        Get word-level inline diff for highlighting changes within lines.

        Returns list of tuples: (change_type, text)
        change_type is one of: "equal", "insert", "delete", "replace"
        """
        old_words = old_text.split()
        new_words = new_text.split()

        result = []
        matcher = difflib.SequenceMatcher(None, old_words, new_words)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                result.append(("equal", " ".join(old_words[i1:i2])))
            elif tag == "delete":
                result.append(("delete", " ".join(old_words[i1:i2])))
            elif tag == "insert":
                result.append(("insert", " ".join(new_words[j1:j2])))
            elif tag == "replace":
                result.append(("delete", " ".join(old_words[i1:i2])))
                result.append(("insert", " ".join(new_words[j1:j2])))

        return result


# Singleton instance
diff_service = DiffService()
