"""
Unit and regression test for kissim's weights CLI.
"""

from pathlib import Path
import pytest
import subprocess

from kissim.utils import enter_temp_directory

PATH_TEST_DATA = Path(__name__).parent / "kissim" / "tests" / "data"


@pytest.mark.parametrize(
    "args",
    [
        f"kissim weights -i {(PATH_TEST_DATA / 'feature_distances_test.csv').absolute()} "
        f"-o fingerprint_distances_test.csv",
        f"kissim weights -i {(PATH_TEST_DATA / 'feature_distances_test.csv').absolute()} "
        f"-o fingerprint_distances_test.csv "
        f"-w 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1",
    ],
)
def test_main_weights(args):
    """
    Test CLI for outliers using subprocesses.
    """

    output = Path("fingerprint_distances_test.csv")  # See -o in CLI command
    args = args.split()

    with enter_temp_directory():
        subprocess.run(args, check=True)

        # Json file there?
        assert output.exists()
        # Log file there?
        assert Path(f"{output.stem}.log").exists()
