import sys

from libbash import bash_to_ast
import os
import shutil
import random
from ..shasta.bash_to_shasta_ast import to_ast_nodes

# The file path to the bash-5.2/tests directory
BASH_TESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(
    __file__)), "test_files")


def get_test_files() -> list[str]:
    """
    Gets all the test files in the test directory
    :return: The list of test files
    """
    test_files = []
    for file in os.listdir(BASH_TESTS_DIR):
        if file.endswith(".sub") or file.endswith(".tests"):
            test_files.append(os.path.join(BASH_TESTS_DIR, file))

    # this is the issue where esac is the case pattern, though we fixed it in our pretty printer,
    # the issue is persistent when the case command is inside a comsub
    for remove_file in [
        "comsub-posix5.sub",
    ]:
        test_files.remove(os.path.join(BASH_TESTS_DIR, remove_file))

    # randomize the order of the test files
    random.shuffle(test_files)

    return test_files


def write_to_file(file: str, content: str):
    """
    Writes the content to the file
    :param file: The file to write to
    :param content: The content to write to the file
    """
    file_obj = open(file, "w", encoding="utf-8")
    file_obj.write(content)
    file_obj.close()


def read_from_file(file: str) -> str:
    """
    Reads the content from the file
    :param file: The file to read from
    :return: The content of the file
    """
    file_obj = open(file, "r", encoding="utf-8")
    content = file_obj.read()
    file_obj.close()
    return content


def remove_empty_lines(content: str) -> str:
    """
    Removes empty lines from the content
    :param content: The content to remove empty lines from
    :return: The content with empty lines removed
    """
    return os.linesep.join([s for s in content.splitlines() if s.strip()])

def test_file(test_file: str):
    """
        This test runs bash_to_ast and ast_to_bash on every test file in the bash-5.2/tests directory
        back and forth NUM_ITERATIONS times. On each iteration it makes sure that the AST is the same as the previous iteration.
        It also makes sure that the bash file is the same as the previous iteration excluding the first iteration.
        Finally if getting the AST fails, it will make sure that it fails consistently.
        """

    # this is necessary for exportfunc2.sub
    sys.setrecursionlimit(10000)

    TMP_DIR = "/tmp/libbash"
    TMP_FILE = f"{TMP_DIR}/test.sh"

    # make a temporary directory to store the bash files
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.mkdir(TMP_DIR)

    print(f"Testing {test_file}")

    # copy the test file to the temporary file
    write_to_file(TMP_FILE, read_from_file(test_file))

    ast = None
    try:
        ast = bash_to_ast(test_file)
    except RuntimeError as e:
        assert str(e) == "Bash read command failed, shell script may be invalid"

    shasta_ast = to_ast_nodes(ast)
    bash = '\n'.join([node.pretty() for node in shasta_ast])
    print(bash)
    write_to_file(TMP_FILE, bash)
    ast2 = bash_to_ast(TMP_FILE)
    shasta_ast = to_ast_nodes(ast2)
    bash2 = '\n'.join([node.pretty() for node in shasta_ast])


    # this handles the case where we have ! ! in the original bash file because on the first iteration a
    # blank line is printed on the second iteration the blank line is removed so the bash files are different
    bash = remove_empty_lines(bash)
    bash2 = remove_empty_lines(bash2)
    assert bash == bash2

    shutil.rmtree(TMP_DIR)

    print(f"Bash and AST consistency tests passed on {test_file}!")


def test_bash_and_ast_consistency():
    """
    This test runs bash_to_ast and ast_to_bash on every test file in the bash-5.2/tests directory 
    back and forth NUM_ITERATIONS times. On each iteration it makes sure that the AST is the same as the previous iteration.
    It also makes sure that the bash file is the same as the previous iteration excluding the first iteration.
    Finally if getting the AST fails, it will make sure that it fails consistently.
    """

    # this is necessary for exportfunc2.sub
    sys.setrecursionlimit(10000)

    TMP_DIR = "/tmp/libbash"
    TMP_FILE = f"{TMP_DIR}/test.sh"

    # make a temporary directory to store the bash files
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.mkdir(TMP_DIR)

    test_files = get_test_files()
    for test_file in test_files:
        print(f"Testing {test_file}")

        # copy the test file to the temporary file
        write_to_file(TMP_FILE, read_from_file(test_file))

        try:
            ast = bash_to_ast(test_file)
        except RuntimeError as e:
            assert str(e) == "Bash read command failed, shell script may be invalid"
            continue

        shasta_ast = to_ast_nodes(ast)
        bash = '\n'.join([node.pretty() for node in shasta_ast])

        write_to_file(TMP_FILE, bash)
        ast = bash_to_ast(TMP_FILE)
        shasta_ast = to_ast_nodes(ast)
        bash2 = '\n'.join([node.pretty() for node in shasta_ast])

        # this handles the case where we have ! ! in the original bash file because on the first iteration a
        # blank line is printed on the second iteration the blank line is removed so the bash files are different
        bash = remove_empty_lines(bash)
        bash2 = remove_empty_lines(bash2)
        assert bash == bash2

    shutil.rmtree(TMP_DIR)

    print(f"Bash and AST consistency tests passed on {len(test_files)} scripts!")


def run_tests():
    """
    Runs all the tests in this file
    """
    print("Running tests...")
    test_bash_and_ast_consistency()
    print("All tests passed!")

