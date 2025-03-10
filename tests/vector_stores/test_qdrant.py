from typing import List, cast

import pytest

try:
    import qdrant_client
except ImportError:
    qdrant_client = None  # type: ignore

from llama_index.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.vector_stores import QdrantVectorStore
from llama_index.vector_stores.qdrant_utils import relative_score_fusion
from llama_index.vector_stores.types import (
    ExactMatchFilter,
    MetadataFilters,
    VectorStoreQuery,
    VectorStoreQueryResult,
)


@pytest.fixture()
def node_embeddings() -> List[TextNode]:
    return [
        TextNode(
            text="lorem ipsum",
            id_="c330d77f-90bd-4c51-9ed2-57d8d693b3b0",
            relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="test-0")},
            metadata={
                "author": "Stephen King",
                "theme": "Friendship",
            },
            embedding=[1.0, 0.0],
        ),
        TextNode(
            text="lorem ipsum",
            id_="c3d1e1dd-8fb4-4b8f-b7ea-7fa96038d39d",
            relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="test-1")},
            metadata={
                "director": "Francis Ford Coppola",
                "theme": "Mafia",
            },
            embedding=[0.0, 1.0],
        ),
    ]


@pytest.mark.skipif(qdrant_client is None, reason="qdrant-client not installed")
def test_add_stores_data(node_embeddings: List[TextNode]) -> None:
    client = qdrant_client.QdrantClient(":memory:")
    qdrant_vector_store = QdrantVectorStore(collection_name="test", client=client)

    with pytest.raises(ValueError):
        client.count("test")  # That indicates the collection does not exist

    qdrant_vector_store.add(node_embeddings)

    assert client.count("test").count == 2


@pytest.mark.skipif(qdrant_client is None, reason="qdrant-client not installed")
def test_add_stores_data_multiple_connections(node_embeddings: List[TextNode]) -> None:
    client = qdrant_client.QdrantClient(":memory:")
    qdrant_vector_store_a = QdrantVectorStore(collection_name="test", client=client)
    qdrant_vector_store_b = QdrantVectorStore(collection_name="test", client=client)

    with pytest.raises(ValueError):
        client.count("test")  # That indicates the collection does not exist

    qdrant_vector_store_a.add([node_embeddings[0]])
    qdrant_vector_store_b.add([node_embeddings[1]])

    assert client.count("test").count == 2


@pytest.mark.skipif(qdrant_client is None, reason="qdrant-client not installed")
def test_build_query_filter_returns_none() -> None:
    client = qdrant_client.QdrantClient(":memory:")
    qdrant_vector_store = QdrantVectorStore(collection_name="test", client=client)

    query = VectorStoreQuery()
    query_filter = qdrant_vector_store._build_query_filter(query)

    assert query_filter is None


@pytest.mark.skipif(qdrant_client is None, reason="qdrant-client not installed")
def test_build_query_filter_returns_match_any() -> None:
    from qdrant_client.http.models import FieldCondition, Filter, MatchAny

    client = qdrant_client.QdrantClient(":memory:")
    qdrant_vector_store = QdrantVectorStore(collection_name="test", client=client)

    query = VectorStoreQuery(doc_ids=["1", "2", "3"])
    query_filter = cast(Filter, qdrant_vector_store._build_query_filter(query))

    assert query_filter is not None
    assert len(query_filter.must) == 1  # type: ignore[index, arg-type]
    assert isinstance(query_filter.must[0], FieldCondition)  # type: ignore[index]
    assert query_filter.must[0].key == "doc_id"  # type: ignore[index]
    assert isinstance(query_filter.must[0].match, MatchAny)  # type: ignore[index]
    assert query_filter.must[0].match.any == ["1", "2", "3"]  # type: ignore[index]


@pytest.mark.skipif(qdrant_client is None, reason="qdrant-client not installed")
def test_build_query_filter_returns_empty_filter_on_query_str() -> None:
    from qdrant_client.http.models import Filter

    client = qdrant_client.QdrantClient(":memory:")
    qdrant_vector_store = QdrantVectorStore(collection_name="test", client=client)

    query = VectorStoreQuery(query_str="lorem")
    query_filter = cast(Filter, qdrant_vector_store._build_query_filter(query))

    assert query_filter is not None
    assert len(query_filter.must) == 0  # type: ignore[index, arg-type]


@pytest.mark.skipif(qdrant_client is None, reason="qdrant-client not installed")
def test_build_query_filter_returns_combined_filter() -> None:
    from qdrant_client.http.models import (
        FieldCondition,
        Filter,
        MatchAny,
        MatchValue,
        Range,
    )

    client = qdrant_client.QdrantClient(":memory:")
    qdrant_vector_store = QdrantVectorStore(collection_name="test", client=client)

    filters = MetadataFilters(
        filters=[
            ExactMatchFilter(key="text_field", value="text_value"),
            ExactMatchFilter(key="int_field", value=4),
            ExactMatchFilter(key="float_field", value=3.5),
        ]
    )
    query = VectorStoreQuery(doc_ids=["1", "2", "3"], filters=filters)
    query_filter = cast(Filter, qdrant_vector_store._build_query_filter(query))

    assert query_filter is not None
    assert len(query_filter.must) == 4  # type: ignore[index, arg-type]

    assert isinstance(query_filter.must[0], FieldCondition)  # type: ignore[index]
    assert query_filter.must[0].key == "doc_id"  # type: ignore[index]
    assert isinstance(query_filter.must[0].match, MatchAny)  # type: ignore[index]
    assert query_filter.must[0].match.any == ["1", "2", "3"]  # type: ignore[index]

    assert isinstance(query_filter.must[1], FieldCondition)  # type: ignore[index]
    assert query_filter.must[1].key == "text_field"  # type: ignore[index]
    assert isinstance(query_filter.must[1].match, MatchValue)  # type: ignore[index]
    assert query_filter.must[1].match.value == "text_value"  # type: ignore[index]

    assert isinstance(query_filter.must[2], FieldCondition)  # type: ignore[index]
    assert query_filter.must[2].key == "int_field"  # type: ignore[index]
    assert isinstance(query_filter.must[2].match, MatchValue)  # type: ignore[index]
    assert query_filter.must[2].match.value == 4  # type: ignore[index]

    assert isinstance(query_filter.must[3], FieldCondition)  # type: ignore[index]
    assert query_filter.must[3].key == "float_field"  # type: ignore[index]
    assert isinstance(query_filter.must[3].range, Range)  # type: ignore[index]
    assert query_filter.must[3].range.gte == 3.5  # type: ignore[index]
    assert query_filter.must[3].range.lte == 3.5  # type: ignore[index]


def test_relative_score_fusion() -> None:
    nodes = [
        TextNode(
            text="lorem ipsum",
            id_="1",
        ),
        TextNode(
            text="lorem ipsum",
            id_="2",
        ),
        TextNode(
            text="lorem ipsum",
            id_="3",
        ),
    ]

    sparse_result = VectorStoreQueryResult(
        ids=["1", "2", "3"],
        similarities=[0.2, 0.3, 0.4],
        nodes=nodes,
    )

    dense_result = VectorStoreQueryResult(
        ids=["3", "2", "1"],
        similarities=[0.8, 0.5, 0.6],
        nodes=nodes[::-1],
    )

    fused_result = relative_score_fusion(dense_result, sparse_result, top_k=3)
    assert fused_result.ids == ["3", "2", "1"]

    # make sparse result empty
    sparse_result = VectorStoreQueryResult(
        ids=[],
        similarities=[],
        nodes=[],
    )

    fused_result = relative_score_fusion(dense_result, sparse_result, top_k=3)
    assert fused_result.ids == ["3", "2", "1"]

    # make both results a single node
    sparse_result = VectorStoreQueryResult(
        ids=["1"],
        similarities=[0.2],
        nodes=[nodes[0]],
    )

    dense_result = VectorStoreQueryResult(
        ids=["1"],
        similarities=[0.8],
        nodes=[nodes[0]],
    )

    fused_result = relative_score_fusion(dense_result, sparse_result, top_k=3)
    assert fused_result.ids == ["1"]

    # test only dense result
    sparse_result = VectorStoreQueryResult(
        ids=[],
        similarities=[],
        nodes=[],
    )

    dense_result = VectorStoreQueryResult(
        ids=["1"],
        similarities=[0.8],
        nodes=[nodes[0]],
    )

    fused_result = relative_score_fusion(dense_result, sparse_result, top_k=3)
    assert fused_result.ids == ["1"]

    # test only sparse result
    sparse_result = VectorStoreQueryResult(
        ids=["1"],
        similarities=[0.88],
        nodes=[nodes[0]],
    )

    dense_result = VectorStoreQueryResult(
        ids=[],
        similarities=[],
        nodes=[],
    )

    fused_result = relative_score_fusion(dense_result, sparse_result, top_k=3)
    assert fused_result.ids == ["1"]

    # test both sparse result and dense result are empty
    sparse_result = VectorStoreQueryResult(
        ids=[],
        similarities=[],
        nodes=[],
    )

    dense_result = VectorStoreQueryResult(
        ids=[],
        similarities=[],
        nodes=[],
    )

    fused_result = relative_score_fusion(dense_result, sparse_result, top_k=3)
    assert fused_result.ids is None
