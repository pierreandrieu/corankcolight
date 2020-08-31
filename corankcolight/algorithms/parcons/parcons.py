from corankcolight.algorithms.median_ranking import MedianRanking
from corankcolight.dataset import Dataset
from corankcolight.scoringscheme import ScoringScheme
from corankcolight.consensus import Consensus, ConsensusFeature
from corankcolight.algorithms.bioconsert.bioconsert import BioConsert
from corankcolight.algorithms.exact.exactalgorithm import ExactAlgorithm
from corankcolight.algorithms.exact.exactalgorithm2 import ExactAlgorithm2
from typing import List, Dict, Tuple
from itertools import combinations
from numpy import vdot, ndarray, count_nonzero, shape, array, zeros, asarray
from igraph import Graph


class ParCons(MedianRanking):
    def __init__(self, algorithm_to_complete=None, bound_for_exact=80):
        if isinstance(algorithm_to_complete, MedianRanking):
            self.alg = algorithm_to_complete
        else:
            self.alg = BioConsert(starting_algorithms=None)
        self.bound_for_exact = bound_for_exact

    def compute_consensus_rankings(
            self,
            dataset: Dataset,
            scoring_scheme: ScoringScheme,
            return_at_most_one_ranking: bool=False,
    ) -> Consensus:
        """
        :param dataset: A dataset containing the rankings to aggregate
        :type dataset: Dataset (class Dataset in package 'datasets')
        :param scoring_scheme: The penalty vectors to consider
        :type scoring_scheme: ScoringScheme (class ScoringScheme in package 'distances')
        :param return_at_most_one_ranking: the algorithm should not return more than one ranking
        :type return_at_most_one_ranking: bool
        :return one or more rankings if the underlying algorithm can find several equivalent consensus rankings
        If the algorithm is not able to provide multiple consensus, or if return_at_most_one_ranking is True then, it
        should return a list made of the only / the first consensus found.
        In all scenario, the algorithm returns a list of consensus rankings
        :raise ScoringSchemeNotHandledException when the algorithm cannot compute the consensus because the
        implementation of the algorithm does not fit with the scoring scheme
        """
        optimal = True
        sc = asarray(scoring_scheme.penalty_vectors_str)
        rankings = dataset.rankings
        res = []
        elem_id = {}
        id_elements = {}
        id_elem = 0
        for ranking in rankings:
            for bucket in ranking:
                for element in bucket:
                    if element not in elem_id:
                        elem_id[element] = id_elem
                        id_elements[id_elem] = element
                        id_elem += 1

        positions = ParCons.__positions(rankings, elem_id)

        gr1, mat_score = self.__graph_of_elements(positions, sc)
        scc = gr1.components()
        for scc_i in scc:
            if len(scc_i) == 1:
                res.append([id_elements.get(scc_i[0])])
            else:
                all_tied = True
                for e1, e2 in combinations(scc_i, 2):
                    if mat_score[e1][e2][2] > mat_score[e1][e2][0] or mat_score[e1][e2][2] > mat_score[e1][e2][1]:
                        all_tied = False
                        break
                if all_tied:
                    buck = []
                    for el in scc_i:
                        buck.append(id_elements.get(el))
                    res.append(buck)
                else:
                    set_scc = set(scc_i)
                    project_rankings = []
                    for ranking in rankings:
                        project_ranking = []
                        for bucket in ranking:
                            project_bucket = []
                            for elem in bucket:
                                if elem_id.get(elem) in set_scc:
                                    project_bucket.append(elem)
                            if len(project_bucket) > 0:
                                project_ranking.append(project_bucket)
                        if len(project_ranking) > 0:
                            project_rankings.append(project_ranking)
                    if len(scc_i) > self.bound_for_exact:
                        cons_ext = self.alg.compute_consensus_rankings(Dataset(project_rankings),
                                                                       scoring_scheme,
                                                                       True).consensus_rankings[0]
                        res.extend(cons_ext)
                        optimal = False
                    else:
                        try:
                            cons_ext = ExactAlgorithm().compute_consensus_rankings(Dataset(project_rankings),
                                                                                   scoring_scheme,
                                                                                   True).consensus_rankings[0]
                        except:
                            cons_ext = ExactAlgorithm2().compute_consensus_rankings(Dataset(project_rankings),
                                                                                    scoring_scheme,
                                                                                    True).consensus_rankings[0]
                        res.extend(cons_ext)
        return Consensus(consensus_rankings=[res],
                         dataset=dataset,
                         scoring_scheme=scoring_scheme,
                         att={ConsensusFeature.IsNecessarilyOptimal: optimal,
                              ConsensusFeature.AssociatedAlgorithm: self.get_full_name()
                              })

    @staticmethod
    def __graph_of_elements(positions: ndarray, matrix_scoring_scheme: ndarray) -> Tuple[Graph, ndarray]:
        graph_of_elements = Graph(directed=True)
        cost_before = matrix_scoring_scheme[0]
        cost_tied = matrix_scoring_scheme[1]
        cost_after = array([cost_before[1], cost_before[0], cost_before[2], cost_before[4], cost_before[3],
                            cost_before[5]])
        n = shape(positions)[0]
        m = shape(positions)[1]
        for i in range(n):
            graph_of_elements.add_vertex(name=str(i))

        matrix = zeros((n, n, 3))
        edges = []
        for e1 in range(n):
            mem = positions[e1]
            d = count_nonzero(mem == -1)
            for e2 in range(e1 + 1, n):
                a = count_nonzero(mem + positions[e2] == -2)
                b = count_nonzero(mem == positions[e2])
                c = count_nonzero(positions[e2] == -1)
                e = count_nonzero(mem < positions[e2])
                relative_positions = array([e - d + a, m - e - b - c + a, b - a, c - a, d - a, a])
                put_before = vdot(relative_positions, cost_before)
                put_after = vdot(relative_positions, cost_after)
                put_tied = vdot(relative_positions, cost_tied)
                if put_before > put_after or put_before > put_tied:
                    edges.append((e2, e1))
                if put_after > put_before or put_after > put_tied:
                    edges.append((e1, e2))
                matrix[e1][e2] = [put_before, put_after, put_tied]
                matrix[e2][e1] = [put_after, put_before, put_tied]
        graph_of_elements.add_edges(edges)
        return graph_of_elements, matrix

    @staticmethod
    def __positions(rankings: List[List[List[int]]], elements_id: Dict) -> ndarray:
        positions = zeros((len(elements_id), len(rankings)), dtype=int) - 1
        id_ranking = 0
        for ranking in rankings:
            id_bucket = 0
            for bucket in ranking:
                for element in bucket:
                    positions[elements_id.get(element)][id_ranking] = id_bucket
                id_bucket += 1
            id_ranking += 1

        return positions

    def get_full_name(self) -> str:
        return "ParCons"

    def is_scoring_scheme_relevant(self, scoring_scheme: ScoringScheme) -> bool:
        return True