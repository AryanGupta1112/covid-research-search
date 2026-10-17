import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from backend.app.search_engine import Document, SearchEngine, tokenize


class RetrievalReferenceTests(unittest.TestCase):
    def engine(self, documents):
        engine = SearchEngine()
        engine.docs = [Document(str(i), '', text) for i, text in enumerate(documents)]
        engine.doc_index = {doc.doc_id: i for i, doc in enumerate(engine.docs)}
        engine._build_indices()
        engine.ready = True
        return engine

    def test_preprocessing_is_applied_to_queries_and_documents(self):
        self.assertEqual(tokenize('THE vaccines, TRANSMISSION!'), ['vaccine', 'transmission'])

    def test_tfidf_matches_independently_computed_cosine(self):
        engine = self.engine(['alpha alpha beta', 'alpha beta beta beta', 'gamma'])
        scores = dict(engine._tfidf('alpha', None))
        idf = math.log(4 / 3) + 1
        first_alpha = (1 + math.log(2)) * idf
        first_beta = idf
        expected = first_alpha / math.sqrt(first_alpha ** 2 + first_beta ** 2)
        self.assertAlmostEqual(scores[0], expected, places=12)
        self.assertGreater(scores[0], scores[1])
        self.assertAlmostEqual(dict(engine._tfidf('alpha alpha beta', None))[0], 1.0)
        self.assertEqual(engine._tfidf('unknown', None), [])

    def test_bm25_matches_hand_calculation(self):
        engine = self.engine(['alpha alpha beta', 'alpha', 'gamma gamma'])
        idf = math.log(1 + (3 - 2 + .5) / (2 + .5))
        expected = idf * (2 * 2.5) / (2 + 1.5 * (.25 + .75 * 3 / 2))
        self.assertAlmostEqual(dict(engine._bm25('alpha', None))[0], expected, places=7)

    def test_rrf_uses_one_based_ranks_and_sixty(self):
        engine = SearchEngine()
        scores = dict(engine._rrf([[(0, 99), (1, 90)], [(1, .5), (2, .4)]], None))
        self.assertAlmostEqual(scores[1], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(scores[0], 1 / 61)
        self.assertEqual(engine._rrf([[(0, 1)], [(1, 1)]], 1)[0][0], 0)

    def test_dense_retrieval_does_not_require_sparse_candidates(self):
        engine = self.engine(['alpha', 'beta', 'gamma'])
        engine.st_model = Mock()
        engine.st_model.encode.return_value = np.array([[1., 0.]], dtype=np.float32)
        engine.dense = np.array([[0., 1.], [1., 0.], [-1., 0.]], dtype=np.float32)
        self.assertEqual(engine._tfidf('unseenword', None), [])
        self.assertEqual(engine._dense('unseenword', None)[0][0], 1)
        self.assertEqual(len(engine._dense('unseenword', None)), 3)

    def test_metrics_keep_missing_relevant_documents_in_denominator(self):
        engine = self.engine(['alpha', 'beta'])
        relevant = {'0', 'outside'}
        grades = {'0': 1, 'outside': 2}
        actual = engine._metrics(['0', '1'], relevant, grades)
        self.assertAlmostEqual(actual['precisionAt10'], .1)
        self.assertAlmostEqual(actual['recallAt100'], .5)
        self.assertAlmostEqual(actual['map'], .5)
        self.assertAlmostEqual(actual['ndcgAt10'], 1 / (3 + 1 / math.log2(3)))

    def test_map_includes_relevant_hits_beyond_rank_one_hundred(self):
        engine = SearchEngine()
        ranked = [str(i) for i in range(101)]
        actual = engine._metrics(ranked, {'100'}, {'100': 1})
        self.assertEqual(actual['recallAt100'], 0)
        self.assertAlmostEqual(actual['map'], 1 / 101)

    def test_evaluation_keeps_queries_with_no_relevant_document_in_index(self):
        engine = self.engine(['alpha'])
        engine.queries = {'q1': 'alpha', 'q2': 'absent'}
        engine.qrels = {'q1': {'0': 1}, 'q2': {'outside': 1}}
        with tempfile.TemporaryDirectory() as tmp:
            engine.data_dir = Path(tmp)
            engine.cache_dir = Path(tmp) / 'cache'
            (engine.data_dir / 'qrels').mkdir()
            (engine.data_dir / 'queries.jsonl').write_text('fixture')
            (engine.data_dir / 'qrels' / 'test.tsv').write_text('fixture')
            result = engine.evaluate()
            self.assertEqual(result['evaluatedQueries'], 2)
            self.assertEqual(result['queriesWithRelevantInIndex'], 1)
            tfidf = next(row for row in result['comparison'] if row['method'] == 'tfidf')
            self.assertEqual(tfidf['map'], .5)
            self.assertEqual(result, engine.evaluate())

    def test_interpolated_pr_has_recall_on_x_and_monotone_precision(self):
        values = SearchEngine._interpolated_precision(['a', 'x', 'b'], {'a', 'b'}, [0, .5, .75, 1])
        np.testing.assert_allclose(values, [1, 1, 2/3, 2/3])
        self.assertTrue(np.all(np.diff(values) <= 0))
        missing = SearchEngine._interpolated_precision(['x'], {'a'}, [0, .5, 1])
        np.testing.assert_allclose(missing, [0, 0, 0])

    def test_empty_rankings_have_zero_metrics(self):
        values = SearchEngine()._metrics([], {'a'}, {'a': 2})
        self.assertTrue(all(value == 0 for value in values.values()))

if __name__ == '__main__':
    unittest.main()
