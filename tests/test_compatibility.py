"""Test compatibility graph and upgrade path logic"""
import pytest
from app.compatibility.graph import UpgradePathEngine


@pytest.fixture
def sample_graph_data():
    """Sample data for testing graph operations"""
    return {
        'model_id': 1,
        'versions': [
            {'id': 1, 'version_string': '4.0.0', 'normalized_version': '4.0.0'},
            {'id': 2, 'version_string': '4.1.0', 'normalized_version': '4.1.0'},
            {'id': 3, 'version_string': '4.2.0', 'normalized_version': '4.2.0'},
            {'id': 4, 'version_string': '4.3.0', 'normalized_version': '4.3.0'},
            {'id': 5, 'version_string': '5.0.0', 'normalized_version': '5.0.0'},
        ],
        'paths': [
            {'from': 1, 'to': 2, 'risk': 'LOW', 'mandatory_intermediates': []},
            {'from': 2, 'to': 3, 'risk': 'LOW', 'mandatory_intermediates': []},
            {'from': 3, 'to': 4, 'risk': 'MED', 'mandatory_intermediates': []},
            {'from': 4, 'to': 5, 'risk': 'HIGH', 'mandatory_intermediates': []},
            # Direct path with mandatory intermediate
            {'from': 1, 'to': 5, 'risk': 'HIGH', 'mandatory_intermediates': [3]},
        ]
    }


def test_upgrade_engine_initialization():
    """Test UpgradePathEngine initialization"""
    engine = UpgradePathEngine()
    assert engine.graph is not None
    assert len(engine.version_map) == 0
    assert len(engine.model_graphs) == 0


def test_manual_graph_building(sample_graph_data):
    """Test manual graph construction"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = sample_graph_data['model_id']
    
    # Build graph manually
    graph = nx.DiGraph()
    version_map = {}
    
    for version in sample_graph_data['versions']:
        graph.add_node(version['id'])
        version_map[version['id']] = version
    
    for path in sample_graph_data['paths']:
        graph.add_edge(
            path['from'],
            path['to'],
            risk_level=path['risk'],
            mandatory_intermediates=path['mandatory_intermediates'],
            requires_backup=True,
            requires_reboot=True
        )
    
    engine.model_graphs[model_id] = graph
    engine.version_map.update(version_map)
    
    assert model_id in engine.model_graphs
    assert engine.model_graphs[model_id].number_of_nodes() == 5
    assert engine.model_graphs[model_id].number_of_edges() == 5


def test_find_upgrade_path_simple(sample_graph_data):
    """Test finding simple upgrade path"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = sample_graph_data['model_id']
    
    # Build graph
    graph = nx.DiGraph()
    for version in sample_graph_data['versions']:
        graph.add_node(version['id'])
        engine.version_map[version['id']] = version
    
    for path in sample_graph_data['paths']:
        graph.add_edge(
            path['from'],
            path['to'],
            risk_level=path['risk'],
            mandatory_intermediates=path['mandatory_intermediates']
        )
    
    engine.model_graphs[model_id] = graph
    
    # Find path from version 1 to version 3
    path = engine.find_upgrade_path(model_id, 1, 3)
    
    assert path is not None
    assert len(path) == 2  # 1->2, 2->3
    assert path[0] == (1, 2)
    assert path[1] == (2, 3)


def test_find_upgrade_path_no_path(sample_graph_data):
    """Test finding path when none exists"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = sample_graph_data['model_id']
    
    # Build graph with no path from 5 to 1 (only forward paths)
    graph = nx.DiGraph()
    for version in sample_graph_data['versions']:
        graph.add_node(version['id'])
        engine.version_map[version['id']] = version
    
    for path in sample_graph_data['paths']:
        graph.add_edge(path['from'], path['to'])
    
    engine.model_graphs[model_id] = graph
    
    # Try to find backward path (should fail)
    path = engine.find_upgrade_path(model_id, 5, 1)
    
    assert path is None


def test_expand_path_with_intermediates(sample_graph_data):
    """Test expanding path with mandatory intermediates"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = sample_graph_data['model_id']
    
    # Build graph
    graph = nx.DiGraph()
    for version in sample_graph_data['versions']:
        graph.add_node(version['id'])
        engine.version_map[version['id']] = version
    
    # Add edge with mandatory intermediate
    graph.add_edge(
        1, 5,
        risk_level='HIGH',
        mandatory_intermediates=[3],  # Must go through version 3
        requires_backup=True
    )
    
    engine.model_graphs[model_id] = graph
    
    # Original path
    path = [(1, 5)]
    
    # Expand
    expanded = engine.expand_path_with_intermediates(model_id, path)
    
    assert len(expanded) == 2  # Should be split into 1->3, 3->5
    assert expanded[0] == (1, 3)
    assert expanded[1] == (3, 5)


def test_get_path_details(sample_graph_data):
    """Test getting detailed path information"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = sample_graph_data['model_id']
    
    # Build graph
    graph = nx.DiGraph()
    for version in sample_graph_data['versions']:
        graph.add_node(version['id'])
        engine.version_map[version['id']] = version
    
    graph.add_edge(
        1, 2,
        risk_level='LOW',
        notes='Simple upgrade',
        estimated_downtime_minutes=30,
        requires_backup=True,
        requires_reboot=True,
        mandatory_intermediates=[]
    )
    
    engine.model_graphs[model_id] = graph
    
    # Get details
    path = [(1, 2)]
    details = engine.get_path_details(model_id, path)
    
    assert len(details) == 1
    assert details[0]['from_version'] == '4.0.0'
    assert details[0]['to_version'] == '4.1.0'
    assert details[0]['risk_level'] == 'LOW'
    assert details[0]['notes'] == 'Simple upgrade'
    assert details[0]['estimated_downtime_minutes'] == 30


def test_calculate_overall_risk():
    """Test overall risk calculation"""
    engine = UpgradePathEngine()
    
    # All LOW risk
    steps = [
        {'risk_level': 'LOW'},
        {'risk_level': 'LOW'}
    ]
    assert engine.calculate_overall_risk(steps) == 'LOW'
    
    # Mix with MED risk
    steps = [
        {'risk_level': 'LOW'},
        {'risk_level': 'MED'}
    ]
    assert engine.calculate_overall_risk(steps) == 'MED'
    
    # Any HIGH risk makes overall HIGH
    steps = [
        {'risk_level': 'LOW'},
        {'risk_level': 'MED'},
        {'risk_level': 'HIGH'}
    ]
    assert engine.calculate_overall_risk(steps) == 'HIGH'


def test_calculate_total_downtime():
    """Test total downtime calculation"""
    engine = UpgradePathEngine()
    
    steps = [
        {'estimated_downtime_minutes': 30},
        {'estimated_downtime_minutes': 45},
        {'estimated_downtime_minutes': 60}
    ]
    
    total = engine.calculate_total_downtime(steps)
    assert total == 135
    
    # With some None values
    steps = [
        {'estimated_downtime_minutes': 30},
        {'estimated_downtime_minutes': None},
        {'estimated_downtime_minutes': 60}
    ]
    
    total = engine.calculate_total_downtime(steps)
    assert total == 90
    
    # All None
    steps = [
        {'estimated_downtime_minutes': None},
        {'estimated_downtime_minutes': None}
    ]
    
    total = engine.calculate_total_downtime(steps)
    assert total is None


def test_validate_path(sample_graph_data):
    """Test path validation"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = sample_graph_data['model_id']
    
    # Build graph
    graph = nx.DiGraph()
    for version in sample_graph_data['versions']:
        graph.add_node(version['id'])
        engine.version_map[version['id']] = version
    
    # Add some edges
    graph.add_edge(1, 2)
    graph.add_edge(2, 3)
    
    engine.model_graphs[model_id] = graph
    
    # Valid path
    valid, error = engine.validate_path(model_id, 1, 3)
    assert valid is True
    assert error is None
    
    # Invalid path (no connection)
    valid, error = engine.validate_path(model_id, 1, 5)
    assert valid is False
    assert error is not None
    
    # Non-existent version
    valid, error = engine.validate_path(model_id, 1, 999)
    assert valid is False
    assert error is not None


def test_complex_path_scenario():
    """Test complex upgrade scenario with multiple intermediates"""
    import networkx as nx
    
    engine = UpgradePathEngine()
    model_id = 1
    
    # Create complex scenario:
    # 1.0 -> 2.0 (simple)
    # 2.0 -> 3.0 (requires intermediate 2.5)
    # 3.0 -> 4.0 (simple but high risk)
    
    graph = nx.DiGraph()
    
    versions = {
        1: '1.0',
        2: '2.0',
        3: '2.5',  # Intermediate
        4: '3.0',
        5: '4.0'
    }
    
    for vid, vstr in versions.items():
        graph.add_node(vid)
        engine.version_map[vid] = {'id': vid, 'version_string': vstr}
    
    # Add edges
    graph.add_edge(1, 2, risk_level='LOW', mandatory_intermediates=[])
    graph.add_edge(2, 4, risk_level='MED', mandatory_intermediates=[3])
    graph.add_edge(4, 5, risk_level='HIGH', mandatory_intermediates=[])
    
    engine.model_graphs[model_id] = graph
    
    # Find path from 1.0 to 4.0
    path = engine.find_upgrade_path(model_id, 1, 5)
    assert path is not None
    
    # Expand with intermediates
    expanded = engine.expand_path_with_intermediates(model_id, path)
    
    # Should have intermediate inserted
    assert len(expanded) > len(path)
    
    # Get details
    details = engine.get_path_details(model_id, expanded)
    assert len(details) > 0
    
    # Calculate risk
    risk = engine.calculate_overall_risk(details)
    assert risk == 'HIGH'  # Because last step is HIGH
