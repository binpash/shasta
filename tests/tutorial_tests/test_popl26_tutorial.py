#!/usr/bin/env python3
"""
Tests for shasta using the popl26-tutorial solution code (steps 1-5).

This test suite verifies:
1. Type checking of the tutorial code with mypy
2. Correct return values from tutorial functions (steps 1-5)

The tutorial code tests parsing, walking, unparsing, subshell counting,
and effect-free analysis of shell scripts.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Path setup - use local files in the same directory
TEST_DIR = Path(__file__).parent
SH_DIR = TEST_DIR / "sh"

# Add test directory to path for local imports
sys.path.insert(0, str(TEST_DIR))

# Import from local solution module
from solution import (
    step1_parse_script,
    step4_subshells,
    is_effect_free,
)
from utils import parse_shell_to_asts, ast_to_code, walk_ast, walk_ast_node
from shasta import ast_node as AST


class TestTypechecking:
    """Type checking tests using mypy."""

    def test_mypy_solution_py(self):
        """Run mypy on solution.py and ensure no type errors."""
        solution_path = TEST_DIR / "solution.py"
        result = subprocess.run(
            [sys.executable, "-m", "mypy", str(solution_path), "--ignore-missing-imports"],
            capture_output=True,
            text=True,
            cwd=str(TEST_DIR),
        )
        # mypy returns 0 on success
        assert result.returncode == 0, f"mypy failed on solution.py:\n{result.stdout}\n{result.stderr}"

    def test_mypy_utils_py(self):
        """Run mypy on utils.py and ensure no type errors."""
        utils_path = TEST_DIR / "utils.py"
        result = subprocess.run(
            [sys.executable, "-m", "mypy", str(utils_path), "--ignore-missing-imports"],
            capture_output=True,
            text=True,
            cwd=str(TEST_DIR),
        )
        assert result.returncode == 0, f"mypy failed on utils.py:\n{result.stdout}\n{result.stderr}"


class TestStep1ParseScript:
    """Tests for step1_parse_script function (parsing shell scripts)."""

    def test_parse_simple_script(self, capsys):
        """Test parsing a simple shell script returns a list of Parsed tuples."""
        script_path = str(SH_DIR / "simple.sh")
        ast = step1_parse_script(script_path)

        assert isinstance(ast, list), "step1_parse_script should return a list"
        assert len(ast) > 0, "Parsed AST should not be empty"

        # Each element should be a 4-tuple (node, text, start_line, end_line)
        for item in ast:
            assert isinstance(item, tuple), "Each parsed item should be a tuple"
            assert len(item) == 4, "Each parsed item should have 4 elements"
            node, text, start_line, end_line = item
            assert isinstance(node, AST.AstNode), "First element should be an AstNode"
            assert isinstance(start_line, int), "Third element should be start line number"
            assert isinstance(end_line, int), "Fourth element should be end line number"

    def test_parse_subshells_script(self, capsys):
        """Test parsing the subshells test script."""
        script_path = str(SH_DIR / "subshells.sh")
        ast = step1_parse_script(script_path)

        assert isinstance(ast, list)
        assert len(ast) > 0

    def test_parse_effectful_script(self, capsys):
        """Test parsing the effectful test script."""
        script_path = str(SH_DIR / "effectful.sh")
        ast = step1_parse_script(script_path)

        assert isinstance(ast, list)
        assert len(ast) > 0


class TestStep2WalkAst:
    """Tests for walk_ast function (AST traversal)."""

    def test_walk_ast_visits_all_nodes(self, capsys):
        """Test that walk_ast visits nodes in the AST."""
        script_path = str(SH_DIR / "simple.sh")
        ast = step1_parse_script(script_path)

        visited_nodes = []

        def collect_nodes(node):
            visited_nodes.append(node)

        walk_ast(ast, visit=collect_nodes)

        assert len(visited_nodes) > 0, "walk_ast should visit nodes"

    def test_walk_ast_node_visits_children(self, capsys):
        """Test that walk_ast_node visits child nodes."""
        script_path = str(SH_DIR / "subshells.sh")
        ast = step1_parse_script(script_path)

        # Get the first node
        first_node = ast[0][0]

        visited = []

        def collect(node):
            visited.append(type(node).__name__)

        walk_ast_node(first_node, visit=collect)

        assert len(visited) > 0, "walk_ast_node should visit at least the root node"


class TestStep3Unparse:
    """Tests for ast_to_code function (unparsing AST to shell code)."""

    def test_unparse_returns_string(self, capsys):
        """Test that ast_to_code returns a string representation of the AST."""
        script_path = str(SH_DIR / "simple.sh")
        ast = step1_parse_script(script_path)

        # Extract just the nodes from the Parsed tuples
        nodes = [node for (node, _, _, _) in ast]
        unparsed = ast_to_code(nodes)

        assert isinstance(unparsed, str), "ast_to_code should return a string"
        assert len(unparsed) > 0, "Unparsed code should not be empty"

    def test_unparse_preserves_shell_constructs(self, capsys):
        """Test that unparsing preserves shell constructs."""
        script_path = str(SH_DIR / "simple.sh")
        ast = step1_parse_script(script_path)

        nodes = [node for (node, _, _, _) in ast]
        unparsed = ast_to_code(nodes)

        # simple.sh contains if/else, for, echo
        # At least some shell keywords should be present
        has_shell_construct = any(kw in unparsed for kw in ["if", "for", "echo", "then", "do"])
        assert has_shell_construct, f"Unparsed code should contain shell constructs: {unparsed}"


class TestStep4Subshells:
    """Tests for step4_subshells function (counting subshells)."""

    def test_subshell_count_in_range(self, capsys):
        """Test that subshell count for subshells.sh is between 4 and 5.

        This is the inline test from solution.py (lines 398-400).
        subshells.sh contains:
        - x=$(echo hi)       # command substitution: 1 subshell (BArgChar)
        - (exit 47)          # subshell: 1 subshell (SubshellNode)
        - sleep 3 &          # background: 1 subshell (BackgroundNode)
        - echo hi | tr a-z A-Z  # pipe: 2 subshells (PipeNode with 2 items)
        Total: 4-5 depending on counting method
        """
        script_path = str(SH_DIR / "subshells.sh")
        ast = step1_parse_script(script_path)

        count = step4_subshells(ast)

        assert isinstance(count, int), "step4_subshells should return an integer"
        assert 4 <= count <= 5, f"subshell count should be 4-5, got {count}"

    def test_simple_script_has_subshells(self, capsys):
        """Test counting subshells in simple.sh (has command substitution)."""
        script_path = str(SH_DIR / "simple.sh")
        ast = step1_parse_script(script_path)

        count = step4_subshells(ast)

        assert isinstance(count, int)
        # simple.sh has $(seq 3) which is a command substitution
        assert count >= 1, "simple.sh should have at least 1 subshell (command substitution)"


class TestStep5EffectFree:
    """Tests for is_effect_free function (effect-free analysis)."""

    def test_is_effect_free_on_effectful_script(self, capsys):
        """Test is_effect_free correctly identifies effectful vs effect-free commands.

        This is the inline test from solution.py (lines 406-411).
        In effectful.sh, only the line with "I am not effectful" should be effect-free.
        """
        script_path = str(SH_DIR / "effectful.sh")
        ast = step1_parse_script(script_path)

        for (node, _, _, _) in ast:
            pretty = node.pretty()
            safe = is_effect_free(node)

            expected_safe = "I am not effectful" in pretty
            assert safe == expected_safe, f"Mismatch for: {pretty!r}, expected safe={expected_safe}, got safe={safe}"

    def test_function_definition_is_effectful(self, capsys):
        """Test that function definitions are considered effectful."""
        script_path = str(SH_DIR / "effectful.sh")
        ast = step1_parse_script(script_path)

        for (node, _, _, _) in ast:
            if isinstance(node, AST.DefunNode):
                assert not is_effect_free(node), "Function definitions should be effectful"

    def test_simple_echo_is_effect_free(self, capsys):
        """Test that a simple echo without side effects is effect-free."""
        script_path = str(SH_DIR / "effectful.sh")
        ast = step1_parse_script(script_path)

        for (node, _, _, _) in ast:
            pretty = node.pretty()
            if "I am not effectful" in pretty:
                assert is_effect_free(node), f"Simple echo should be effect-free: {pretty}"

    def test_assignment_is_effectful(self, capsys):
        """Test that assignments are considered effectful."""
        script_path = str(SH_DIR / "effectful.sh")
        ast = step1_parse_script(script_path)

        for (node, _, _, _) in ast:
            pretty = node.pretty()
            if "bare assignment" in pretty.lower():
                assert not is_effect_free(node), f"Assignment should be effectful: {pretty}"


class TestIntegration:
    """Integration tests running multiple steps together."""

    def test_parse_unparse_roundtrip(self, capsys):
        """Test that parsing and unparsing produces valid shell code."""
        script_path = str(SH_DIR / "simple.sh")

        # Step 1: Parse
        ast = step1_parse_script(script_path)
        assert len(ast) > 0

        # Step 3: Unparse
        nodes = [node for (node, _, _, _) in ast]
        unparsed = ast_to_code(nodes)
        assert len(unparsed) > 0

        # The unparsed code should be valid (can be re-parsed)
        # Write to temp file and parse again
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(unparsed)
            temp_path = f.name

        try:
            # Re-parse should succeed
            ast2 = list(parse_shell_to_asts(temp_path))
            assert len(ast2) > 0, "Re-parsed AST should not be empty"
        finally:
            import os
            os.unlink(temp_path)

    def test_full_pipeline_subshells(self, capsys):
        """Test running steps 1-4 on subshells.sh."""
        script_path = str(SH_DIR / "subshells.sh")

        # Step 1: Parse
        ast = step1_parse_script(script_path)
        assert isinstance(ast, list) and len(ast) > 0

        # Step 3: Unparse
        nodes = [node for (node, _, _, _) in ast]
        unparsed = ast_to_code(nodes)
        assert isinstance(unparsed, str) and len(unparsed) > 0

        # Step 4: Count subshells
        count = step4_subshells(ast)
        assert 4 <= count <= 5

    def test_full_pipeline_effectful(self, capsys):
        """Test running steps 1-5 on effectful.sh."""
        script_path = str(SH_DIR / "effectful.sh")

        # Step 1: Parse
        ast = step1_parse_script(script_path)
        assert isinstance(ast, list) and len(ast) > 0

        # Step 5: Check effect-free analysis
        effect_free_count = 0
        effectful_count = 0
        for (node, _, _, _) in ast:
            if is_effect_free(node):
                effect_free_count += 1
            else:
                effectful_count += 1

        # effectful.sh has 1 effect-free command ("I am not effectful")
        # and multiple effectful ones
        assert effect_free_count == 1, f"Expected 1 effect-free command, got {effect_free_count}"
        assert effectful_count > 0, "Should have multiple effectful commands"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
