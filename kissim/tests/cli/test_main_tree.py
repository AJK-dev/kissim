"""
Unit and regression test for kissim's tree CLI.
"""

from pathlib import Path
import pytest
import subprocess

from kissim.utils import enter_temp_directory
from kissim.encoding import Fingerprint, FingerprintGenerator

PATH_TEST_DATA = Path(__name__).parent / "kissim" / "tests" / "data"


@pytest.mark.parametrize(
    "args",
    [
        f"kissim tree -i {(PATH_TEST_DATA / 'kinase_matrix.csv').absolute()} -o kissim.tree",
        f"kissim tree -i {(PATH_TEST_DATA / 'kinase_matrix.csv').absolute()} -o kissim.tree -c centroid",
    ],
)
def test_encode(args):
    """
    Test CLI for encoding using subprocesses.
    """

    tree_path = Path("kissim.tree")
    annotation_path = Path("kinase_annotations.csv")

    args = args.split()

    with enter_temp_directory():
        subprocess.run(args, check=True)

        # Tree file there?
        assert tree_path.exists()
        # Annotation file there?
        assert annotation_path.exists()

        # Load files?


@pytest.mark.parametrize(
    "args",
    [
        f"kissim tree -i {(PATH_TEST_DATA / 'kinase_matrix.csv').absolute()} -o kissim.tree -c xxx",
    ],
)
def test_encode_error(args):
    """
    Test if input arguments cause error.
    """

    args = args.split()

    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(args, check=True)
