"""
kissim.comparison.fingerprint_distance_generator

Defines the pairwise fingerprint distances for a set of fingerprints.
"""

import datetime
from itertools import repeat
import json
import ijson
import logging
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from kissim.comparison import FingerprintDistance, FeatureDistancesGenerator
from kissim.comparison.utils import format_weights
from kissim.utils import set_n_cores

logger = logging.getLogger(__name__)


class FingerprintDistanceGenerator:
    """
    Generate fingerprint distances for multiple fingerprint pairs based on their feature distances,
    given a feature weighting scheme.
    Uses parallel computing of fingerprint pairs.

    Attributes
    ----------
    structure_kinase_ids : list of tuple
        Structure and kinase IDs for structures in dataset.
    feature_weights : None or list of float
        Feature weights of the following form:
        (i) None
            Default feature weights: All features equally distributed to 1/15
            (15 features in total).
        (ii) By feature (list of 15 floats):
            Features to be set in the following order: size, hbd, hba, charge, aromatic,
            aliphatic, sco, exposure, distance_to_centroid, distance_to_hinge_region,
            distance_to_dfg_region, distance_to_front_pocket, moment1, moment2, and moment3.
            All floats must sum up to 1.0.
    _structures1 : list of int
        List of first part of structure pairs.
    _structures2 : list of int
        List of second part of structure pairs.
    _kinase1 : list of str
        List of kinases belonging to first part of structure pairs.
    _kinase2 : list of str
        List of kinases belonging to second part of structure pairs.
    _distances : np.array
        Fingerprint distances for structure pairs.
    _bit_coverages : np.array
        Bit coverages for structure pairs.
    """

    def __init__(self, **kwargs):

        self.structure_kinase_ids = None
        self.feature_weights = None
        self._structures1 = None
        self._structures2 = None
        self._kinases1 = None
        self._kinases2 = None
        self._distances = None
        self._bit_coverages = None

    def __eq__(self, other):

        if isinstance(other, FingerprintDistanceGenerator):
            return (
                self.structure_kinase_ids == other.structure_kinase_ids
                and np.array_equal(self.feature_weights, other.feature_weights)
                and self._structures1 == other._structures1
                and self._structures2 == other._structures2
                and self._kinases1 == other._kinases1
                and self._kinases2 == other._kinases2
                and np.array_equal(self._distances, other._distances, equal_nan=True)
                and np.array_equal(self._bit_coverages, other._bit_coverages, equal_nan=True)
            )

    @property
    def structure_ids(self):
        """
        Unique structure IDs associated with all fingerprints (sorted alphabetically).

        Returns
        -------
        list of str or int
            Structure IDs.
        """

        return sorted(
            pd.DataFrame(self.structure_kinase_ids, columns=["structure_id", "kinase_id"])[
                "structure_id"
            ].unique()
        )

    @property
    def kinase_ids(self):
        """
        Unique kinase IDs (e.g. kinase names) associated with all fingerprints (sorted
        alphabetically).

        Returns
        -------
        list of str or int
            Kinase IDs.
        """

        return sorted(
            pd.DataFrame(self.structure_kinase_ids, columns=["structure_id", "kinase_id"])[
                "kinase_id"
            ].unique()
        )

    @property
    def data(self):
        """
        Fingerprint distance data for all fingerprint pairs.

        Returns
        -------
        pandas.DataFrame
            Fingerprint distance and coverage, plus details on both molecule codes associated with
            fingerprint pairs.
        """

        return pd.DataFrame(
            {
                "structure1": self._structures1,
                "structure2": self._structures2,
                "kinase1": self._kinases1,
                "kinase2": self._kinases2,
                "distance": self._distances,
                "coverage": self._bit_coverages,
            }
        )

    @classmethod
    def from_feature_distances_generator(
        cls, feature_distances_generator, feature_weights=None, n_cores=1
    ):
        """
        Generate fingerprint distances for multiple fingerprint pairs based on their feature
        distances, given a feature weighting scheme.
        Uses parallel computing of fingerprint pairs.

        Parameters
        ----------
        feature_distances_generator : kissim.similarity.FeatureDistancesGenerator
            Feature distances for multiple fingerprint pairs.
        feature_weights : None or list of float
            Feature weights of the following form:
            (i) None
                Default feature weights: All features equally distributed to 1/15
                (15 features in total).
            (ii) By feature (list of 15 floats):
                Features to be set in the following order: size, hbd, hba, charge, aromatic,
                aliphatic, sco, exposure, distance_to_centroid, distance_to_hinge_region,
                distance_to_dfg_region, distance_to_front_pocket, moment1, moment2, and moment3.
                All floats must sum up to 1.0.
        n_cores : int or None
            Number of cores to be used for fingerprint generation as defined by the user.

        Returns
        -------
        kissim.comparison.FingerprintDistanceGenerator
            Fingerprint distance generator.
        """

        logger.info("GENERATE FINGERPRINT DISTANCES")
        logger.info(f"Number of input feature distances: {len(feature_distances_generator.data)}")

        start_time = datetime.datetime.now()
        logger.info(f"Fingerprint distance generation started at: {start_time}")

        # Set number of cores to be used
        n_cores = set_n_cores(n_cores)

        # Format input feature weights
        feature_weights = format_weights(feature_weights)
        logger.info(f"Feature weights: {feature_weights}")

        fingerprint_distance_generator = cls()

        # Calculate pairwise fingerprint distances
        fingerprint_distance_list = (
            fingerprint_distance_generator._get_fingerprint_distance_from_list(
                fingerprint_distance_generator._get_fingerprint_distance,
                feature_distances_generator.data,
                feature_weights,
                n_cores,
            )
        )

        # Set class attributes
        fingerprint_distance_generator.feature_weights = feature_weights
        fingerprint_distance_generator.structure_kinase_ids = (
            feature_distances_generator.structure_kinase_ids
        )
        fingerprint_distance_generator._structures1 = []
        fingerprint_distance_generator._structures2 = []
        fingerprint_distance_generator._kinases1 = []
        fingerprint_distance_generator._kinases2 = []
        fingerprint_distance_generator._distances = []
        fingerprint_distance_generator._bit_coverages = []
        for fingerprint_distance in fingerprint_distance_list:
            fingerprint_distance_generator._structures1.append(
                fingerprint_distance.structure_pair_ids[0]
            )
            fingerprint_distance_generator._structures2.append(
                fingerprint_distance.structure_pair_ids[1]
            )
            fingerprint_distance_generator._kinases1.append(
                fingerprint_distance.kinase_pair_ids[0]
            )
            fingerprint_distance_generator._kinases2.append(
                fingerprint_distance.kinase_pair_ids[1]
            )
            fingerprint_distance_generator._distances.append(fingerprint_distance.distance)
            fingerprint_distance_generator._bit_coverages.append(fingerprint_distance.bit_coverage)
        fingerprint_distance_generator._distances = np.array(
            fingerprint_distance_generator._distances
        )
        fingerprint_distance_generator._bit_coverages = np.array(
            fingerprint_distance_generator._bit_coverages
        )

        logger.info(
            f"Number of output fingerprint distances: {len(fingerprint_distance_generator.data)}"
        )

        end_time = datetime.datetime.now()
        logger.info(f"Runtime: {end_time - start_time}")

        return fingerprint_distance_generator

    @classmethod
    def from_structure_klifs_ids(
        cls, structure_klifs_ids, klifs_session=None, feature_weights=None, n_cores=1
    ):
        """
        Calculate fingerprint distances for all possible structure pairs.

        Parameters
        ----------
        structure_klifs_id : int
            Input structure KLIFS ID (output fingerprints may contain less IDs because some
            structures could not be encoded).
        klifs_session : opencadd.databases.klifs.session.Session
            Local or remote KLIFS session.
        feature_weights : None or list of float
            Feature weights of the following form:
            (i) None
                Default feature weights: All features equally distributed to 1/15
                (15 features in total).
            (ii) By feature (list of 15 floats):
                Features to be set in the following order: size, hbd, hba, charge, aromatic,
                aliphatic, sco, exposure, distance_to_centroid, distance_to_hinge_region,
                distance_to_dfg_region, distance_to_front_pocket, moment1, moment2, and moment3.
                All floats must sum up to 1.0.
        n_cores : int or None
            Number of cores to be used for fingerprint generation as defined by the user.

        Returns
        -------
        kissim.comparison.FingerprintDistancesGenerator
            Fingerprint distance generator.
        """

        feature_distances_generator = FeatureDistancesGenerator.from_structure_klifs_ids(
            structure_klifs_ids, klifs_session, n_cores
        )
        fingerprint_distance_generator = cls.from_feature_distances_generator(
            feature_distances_generator, feature_weights, n_cores
        )
        return fingerprint_distance_generator

    @classmethod
    def from_json(cls, filepath):
        """
        Initialize a FingerprintDistanceGenerator object from a json file.

        Parameters
        ----------
        filepath : str or pathlib.Path
            Path to json file.

        Returns
        -------
        kissim.comparison.FingerprintDistanceGenerator
            Fingerprint distance generator.
        """

        # Load JSON string
        filepath = Path(filepath)
        with open(filepath, "r") as f:
            json_string = f.read()
        fingerprint_distance_generator_dict = json.loads(json_string)

        # Initialize object attributes from dict
        fingerprint_distance_generator = cls()
        fingerprint_distance_generator.__dict__.update(fingerprint_distance_generator_dict)
        # Update some attributes
        fingerprint_distance_generator.structure_kinase_ids = [
            tuple(i) for i in fingerprint_distance_generator.structure_kinase_ids
        ]
        fingerprint_distance_generator.feature_weights = np.array(
            fingerprint_distance_generator.feature_weights, dtype=np.float
        )
        fingerprint_distance_generator._distances = np.array(
            fingerprint_distance_generator._distances, dtype=np.float
        )
        fingerprint_distance_generator._bit_coverages = np.array(
            fingerprint_distance_generator._bit_coverages, dtype=np.float
        )

        return fingerprint_distance_generator

    def to_json(self, filepath):
        """
        Write FingerprintDistanceGenerator class attributes to a json file.

        Parameters
        ----------
        filepath : str or pathlib.Path
            Path to json file.
        """

        fingerprint_distance_generator_dict = self.__dict__.copy()
        fingerprint_distance_generator_dict[
            "feature_weights"
        ] = fingerprint_distance_generator_dict["feature_weights"].tolist()
        fingerprint_distance_generator_dict["_distances"] = fingerprint_distance_generator_dict[
            "_distances"
        ].tolist()
        fingerprint_distance_generator_dict[
            "_bit_coverages"
        ] = fingerprint_distance_generator_dict["_bit_coverages"].tolist()
        json_string = json.dumps(fingerprint_distance_generator_dict)

        filepath = Path(filepath)
        with open(filepath, "w") as f:
            f.write(json_string)

    @staticmethod
    def _get_fingerprint_distance_from_list(
        _get_fingerprint_distance, feature_distances_list, feature_weights=None, n_cores=1
    ):
        """
        Get fingerprint distances based on multiple feature distances
        (i.e. for multiple fingerprint pairs).
        Uses parallel computing.

        Parameters
        ----------
        _get_fingerprint_distance : method
            Method calculating fingerprint distance for one fingerprint pair
            (based on their feature distances).
        feature_distances_list : list of kissim.similarity.FeatureDistances
            List of distances and bit coverages between two fingerprints for each of their
            features.
        feature_weights : None or list of float
            Feature weights of the following form:
            (i) None
                Default feature weights: All features equally distributed to 1/15
                (15 features in total).
            (ii) By feature (list of 15 floats):
                Features to be set in the following order: size, hbd, hba, charge, aromatic,
                aliphatic, sco, exposure, distance_to_centroid, distance_to_hinge_region,
                distance_to_dfg_region, distance_to_front_pocket, moment1, moment2, and moment3.
                All floats must sum up to 1.0.
        n_cores : int or None
            Number of cores to be used for fingerprint generation as defined by the user.

        Returns
        -------
        list of kissim.similarity.FingerprintDistance
            List of distance between two fingerprints, plus details on molecule codes, feature
            weights and feature coverage.
        """

        pool = Pool(processes=n_cores)
        fingerprint_distances_list = pool.starmap(
            _get_fingerprint_distance, zip(feature_distances_list, repeat(feature_weights))
        )
        pool.close()
        pool.join()

        return fingerprint_distances_list

    @staticmethod
    def _get_fingerprint_distance(feature_distances, feature_weights=None):
        """
        Get the fingerprint distance for one fingerprint pair.

        Parameters
        ----------
        feature_distances : kissim.similarity.FeatureDistances
            Distances and bit coverages between two fingerprints for each of their features.
        feature_weights : None or list of float
            Feature weights of the following form:
            (i) None
                Default feature weights: All features equally distributed to 1/15
                (15 features in total).
            (ii) By feature (list of 15 floats):
                Features to be set in the following order: size, hbd, hba, charge, aromatic,
                aliphatic, sco, exposure, distance_to_centroid, distance_to_hinge_region,
                distance_to_dfg_region, distance_to_front_pocket, moment1, moment2, and moment3.
                All floats must sum up to 1.0.

        Returns
        -------
        kissim.similarity.FingerprintDistance
            Distance between two fingerprints, plus details on molecule codes, feature weights and
            feature coverage.
        """

        fingerprint_distance = FingerprintDistance.from_feature_distances(
            feature_distances, feature_weights
        )

        return fingerprint_distance

    def structure_distance_matrix(self):
        """
        Get fingerprint distances for all structure pairs in the form of a matrix (DataFrame).

        Parameters
        ----------
        fill : bool
            Fill or fill not (default) lower triangle of distance matrix.

        Returns
        -------
        pandas.DataFrame
            Structure distance matrix.
        """

        # Data for upper half of the matrix
        pairs_upper = self.data[["structure1", "structure2", "distance"]]
        # Data for lower half of the matrix
        pairs_lower = pairs_upper.rename(
            columns={"structure1": "structure2", "structure2": "structure1"}
        )

        # Concatenate upper and lower matrix data
        pairs = pd.concat([pairs_upper, pairs_lower]).sort_values(["structure1", "structure2"])
        # Convert to matrix
        matrix = pairs.pivot(columns="structure2", index="structure1", values="distance")
        # Matrix diagonal is NaN > set to 0.0
        matrix = matrix.fillna(0.0)

        return matrix

    def kinase_distance_matrix(self, by="minimum"):
        """
        Extract per kinase pair one distance value from the set of structure pair distance values
        and return these  fingerprint distances for all kinase pairs in the form of a matrix
        (DataFrame).

        Parameters
        ----------
        by : str
            Condition on which the distance value per kinase pair is extracted from the set of
            distances values per structure pair. Default: Minimum distance value.

        Returns
        -------
        pandas.DataFrame
            Kinase distance matrix.
        """

        # Data for upper half of the matrix
        pairs_upper = self.kinase_distances(by).reset_index()[["kinase1", "kinase2", "distance"]]
        # Data for lower half of the matrix
        pairs_lower = pairs_upper.rename(columns={"kinase1": "kinase2", "kinase2": "kinase1"})

        # Concatenate upper and lower matrix data
        pairs = (
            pd.concat([pairs_upper, pairs_lower])
            .sort_values(["kinase1", "kinase2"])
            .drop_duplicates()
            .reset_index(drop=True)
        )

        # Convert to matrix
        matrix = pairs.pivot(columns="kinase2", index="kinase1", values="distance")
        # Matrix diagonal is NaN > set to 0.0
        matrix = matrix.fillna(0.0)

        return matrix

    def kinase_distances(self, by="minimum"):
        """
        Extract per kinase pair one distance value from the set of structure pair distance values.

        Parameters
        ----------
        by : str
            Condition on which the distance value per kinase pair is extracted from the set of
            distances values per structure pair. Default: Minimum distance value.

        Returns
        -------
        pandas.DataFrame
            Fingerprint distance and coverage for kinase pairs.
        """

        # Add self-comparisons
        data = self.data
        data_self_comparisons = pd.DataFrame(
            [
                [structure_id, structure_id, kinase_id, kinase_id, 0.0, np.nan]
                for (
                    structure_id,
                    kinase_id,
                ) in self.structure_kinase_ids
            ],
            columns=["structure1", "structure2", "kinase1", "kinase2", "distance", "coverage"],
        )
        data = pd.concat([data, data_self_comparisons])

        # Group by kinase names
        structure_distances_grouped_by_kinases = data.groupby(
            by=["kinase1", "kinase2"], sort=False
        )

        # Get distance values per kinase pair based on given condition
        by_terms = "minimum maximum mean size".split()

        if by == "minimum":
            kinase_distances = structure_distances_grouped_by_kinases.min()
            kinase_distances = kinase_distances.reset_index().set_index(
                ["kinase1", "kinase2", "structure1", "structure2"]
            )
        elif by == "maximum":
            kinase_distances = structure_distances_grouped_by_kinases.max()
            kinase_distances = kinase_distances.reset_index().set_index(
                ["kinase1", "kinase2", "structure1", "structure2"]
            )
        elif by == "mean":
            kinase_distances = structure_distances_grouped_by_kinases.mean()
            kinase_distances = kinase_distances.reset_index().set_index(["kinase1", "kinase2"])
        elif by == "size":
            kinase_distances = structure_distances_grouped_by_kinases.size()
            kinase_distances.name = "distance"
            kinase_distances = kinase_distances.reset_index().set_index(["kinase1", "kinase2"])
        else:
            raise ValueError(f'Condition "by" unknown. Choose from: {", ".join(by_terms)}')

        return kinase_distances
