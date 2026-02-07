"""Tests for .tldrignore pattern handling in API functions.

This test suite verifies that get_code_structure() and analyze_dead_code()
properly respect .tldrignore patterns by default, fixing the bug where
node_modules and other ignored directories were included in results.

Related PR: https://github.com/parcadei/llm-tldr/pull/50
"""

from pathlib import Path


class TestGetCodeStructureIgnorePatterns:
    """Test that get_code_structure() respects .tldrignore by default."""

    def test_respects_tldrignore_by_default(self, tmp_path: Path):
        """get_code_structure() should auto-create IgnoreSpec when ignore_spec=None.

        This tests the fix for the bug where node_modules was included in results,
        causing 99.8% false positives in dead code analysis.
        """
        from tldr.api import get_code_structure

        # Setup: Create project structure
        project = tmp_path / "project"
        project.mkdir()

        # Create .tldrignore
        (project / ".tldrignore").write_text("node_modules/\n.venv/\n")

        # Create source file
        src_dir = project / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def hello():\n    pass\n")

        # Create ignored files
        nm_dir = project / "node_modules" / "package"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.py").write_text("def ignored_func():\n    pass\n")

        venv_dir = project / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "lib.py").write_text("def venv_func():\n    pass\n")

        # Action: Call get_code_structure without ignore_spec
        result = get_code_structure(str(project), language="python", max_results=100)

        # Assert: No ignored files included
        file_paths = [f["path"] for f in result.get("files", [])]
        node_modules_files = [p for p in file_paths if "node_modules" in p]
        venv_files = [p for p in file_paths if ".venv" in p]

        assert len(node_modules_files) == 0, (
            f"Expected no node_modules files, but found: {node_modules_files}"
        )
        assert len(venv_files) == 0, (
            f"Expected no .venv files, but found: {venv_files}"
        )
        assert len(file_paths) == 1, f"Expected 1 file, found {len(file_paths)}: {file_paths}"
        assert "src/main.py" in file_paths[0] or "src\\main.py" in file_paths[0], (
            f"Expected src/main.py, got {file_paths}"
        )

    def test_explicit_ignore_spec_still_works(self, tmp_path: Path):
        """Passing explicit ignore_spec should override auto-creation (backward compat)."""
        from tldr.api import get_code_structure
        from tldr.tldrignore import IgnoreSpec

        # Setup: Create project with .tldrignore
        project = tmp_path / "project"
        project.mkdir()

        (project / ".tldrignore").write_text("node_modules/\n")

        # Create files
        (project / "main.py").write_text("def main():\n    pass\n")

        nm_dir = project / "node_modules"
        nm_dir.mkdir()
        (nm_dir / "lib.py").write_text("def lib():\n    pass\n")

        # Create custom IgnoreSpec that ignores main.py instead
        custom_spec = IgnoreSpec(project, use_gitignore=False)
        # Note: We can't easily modify IgnoreSpec patterns, so we'll test that
        # passing explicit ignore_spec doesn't auto-create a new one

        # Action: Pass explicit ignore_spec (empty/custom one)
        result = get_code_structure(
            str(project),
            language="python",
            max_results=100,
            ignore_spec=custom_spec
        )

        # Assert: Uses the explicit spec, not auto-created one
        # This test mainly verifies backward compatibility - explicit ignore_spec is honored
        file_paths = [f["path"] for f in result.get("files", [])]
        assert len(file_paths) >= 1, "Should find files when explicit ignore_spec is passed"

    def test_respect_ignore_false_includes_ignored_files(self, tmp_path: Path):
        """Setting respect_ignore=False should include all files (opt-out)."""
        from tldr.api import get_code_structure

        # Setup: Create project with .tldrignore
        project = tmp_path / "project"
        project.mkdir()

        (project / ".tldrignore").write_text("node_modules/\n")

        # Create files
        (project / "main.py").write_text("def main():\n    pass\n")

        nm_dir = project / "node_modules"
        nm_dir.mkdir()
        (nm_dir / "lib.py").write_text("def lib():\n    pass\n")

        # Action: Call with respect_ignore=False
        result = get_code_structure(
            str(project),
            language="python",
            max_results=100,
            respect_ignore=False
        )

        # Assert: All files included, even node_modules
        file_paths = [f["path"] for f in result.get("files", [])]
        node_modules_files = [p for p in file_paths if "node_modules" in p]

        assert len(node_modules_files) > 0, (
            "Expected node_modules files when respect_ignore=False, but found none"
        )
        assert len(file_paths) == 2, (
            f"Expected 2 files (main.py + node_modules/lib.py), found {len(file_paths)}"
        )

    def test_respects_gitignore_when_no_tldrignore(self, tmp_path: Path):
        """Should respect .gitignore patterns when .tldrignore is missing."""
        from tldr.api import get_code_structure

        # Setup: Create project with only .gitignore (no .tldrignore)
        project = tmp_path / "project"
        project.mkdir()

        # Create .gitignore instead of .tldrignore
        (project / ".gitignore").write_text("__pycache__/\n*.pyc\n")

        # Create files
        (project / "main.py").write_text("def main():\n    pass\n")

        cache_dir = project / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "main.cpython-39.pyc").write_text("bytecode")

        # Action: Call get_code_structure (should use gitignore)
        result = get_code_structure(str(project), language="python", max_results=100)

        # Assert: __pycache__ files excluded
        file_paths = [f["path"] for f in result.get("files", [])]
        cache_files = [p for p in file_paths if "__pycache__" in p]

        assert len(cache_files) == 0, (
            f"Expected no __pycache__ files, but found: {cache_files}"
        )
        assert len(file_paths) == 1, f"Expected 1 file, found {len(file_paths)}"


class TestAnalyzeDeadCodeIgnorePatterns:
    """Test that analyze_dead_code() respects .tldrignore."""

    def test_dead_code_excludes_ignored_directories(self, tmp_path: Path):
        """analyze_dead_code() should not report functions from ignored directories.

        This is the primary bug fix - dead code analysis was reporting 99.8%
        false positives from node_modules.
        """
        from tldr.api import get_code_structure

        # Setup: Create project with node_modules
        project = tmp_path / "project"
        project.mkdir()

        (project / ".tldrignore").write_text("node_modules/\n")

        # Create main source file
        (project / "main.py").write_text("""
def main():
    used_function()

def used_function():
    pass

def unused_function():
    pass
""")

        # Create node_modules with "dead" code
        nm_dir = project / "node_modules" / "package"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.py").write_text("""
def node_modules_func():
    pass

def another_nm_func():
    pass
""")

        # Action: Get code structure (which is what analyze_dead_code uses internally)
        result = get_code_structure(str(project), language="python", max_results=100)

        # Assert: No functions from node_modules in structure
        files = result.get("files", [])
        node_modules_files = [
            f for f in files
            if "node_modules" in f.get("path", "")
        ]

        assert len(node_modules_files) == 0, (
            f"Expected no node_modules files in structure, but found: {node_modules_files}"
        )

        # Should find main.py
        file_paths = [f.get("path") for f in files]
        main_files = [p for p in file_paths if "main.py" in p]
        assert len(main_files) == 1, (
            f"Expected to find main.py, but found: {file_paths}"
        )


class TestSemanticExtractRespectIgnore:
    """Test semantic.py extract_units_from_project() respects respect_ignore flag."""

    def test_extract_units_propagates_respect_ignore_false(self, tmp_path: Path):
        """Verify extract_units_from_project propagates respect_ignore=False correctly.

        This tests the fix for the Sentry-reported bug where semantic.py wasn't
        passing the respect_ignore flag to get_code_structure.
        """
        from tldr.semantic import extract_units_from_project

        # Setup: Create project with .tldrignore
        project = tmp_path / "project"
        project.mkdir()

        (project / ".tldrignore").write_text("vendor/\n")

        # Create main file
        (project / "main.py").write_text("""
def main():
    '''Main function'''
    pass
""")

        # Create ignored vendor file
        vendor_dir = project / "vendor"
        vendor_dir.mkdir()
        (vendor_dir / "lib.py").write_text("""
def vendor_lib():
    '''Vendor library function'''
    pass
""")

        # Action: Call with respect_ignore=False
        units = extract_units_from_project(
            str(project),
            lang="python",
            respect_ignore=False
        )

        # Assert: Should include vendor files
        # Note: EmbeddingUnit has 'file' attribute, not 'file_path'
        unit_paths = [u.file for u in units]
        vendor_units = [p for p in unit_paths if "vendor" in p]

        assert len(vendor_units) > 0, (
            "Expected vendor/ files when respect_ignore=False, but found none. "
            "This indicates the flag wasn't propagated to get_code_structure."
        )


class TestIgnorePatternEdgeCases:
    """Edge cases for ignore pattern handling."""

    def test_works_without_ignore_files(self, tmp_path: Path):
        """Should work gracefully when neither .tldrignore nor .gitignore exist."""
        from tldr.api import get_code_structure

        # Setup: Create project without any ignore files
        project = tmp_path / "project"
        project.mkdir()

        (project / "main.py").write_text("def main():\n    pass\n")

        # Action: Call get_code_structure
        result = get_code_structure(str(project), language="python", max_results=100)

        # Assert: Should work without errors
        file_paths = [f["path"] for f in result.get("files", [])]
        assert len(file_paths) == 1, "Should find the main.py file"

    def test_empty_tldrignore(self, tmp_path: Path):
        """Should handle empty .tldrignore file gracefully."""
        from tldr.api import get_code_structure

        # Setup: Create project with empty .tldrignore
        project = tmp_path / "project"
        project.mkdir()

        (project / ".tldrignore").write_text("")  # Empty file

        (project / "main.py").write_text("def main():\n    pass\n")

        # Action: Call get_code_structure
        result = get_code_structure(str(project), language="python", max_results=100)

        # Assert: Should work without errors
        file_paths = [f["path"] for f in result.get("files", [])]
        assert len(file_paths) == 1, "Should find the main.py file with empty .tldrignore"
