"""Compatibility graph and upgrade path computation"""
from typing import List, Dict, Any, Optional, Tuple
import networkx as nx
from collections import deque
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Model, SoftwareVersion, UpgradePath, ModelVersionCompatibility

logger = logging.getLogger(__name__)


class UpgradePathEngine:
    """Deterministic upgrade path computation using directed graph"""
    
    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        self.version_map: Dict[int, Dict[str, Any]] = {}  # version_id -> version data
        self.model_graphs: Dict[int, nx.DiGraph] = {}  # model_id -> graph
    
    async def build_graph_from_db(self, db: AsyncSession, model_id: int) -> None:
        """
        Build compatibility graph from database for a specific model.
        
        Args:
            db: Database session
            model_id: Model ID to build graph for
        """
        # Get all versions for this model
        result = await db.execute(
            select(SoftwareVersion)
            .where(SoftwareVersion.model_id == model_id)
            .order_by(SoftwareVersion.normalized_version)
        )
        versions = result.scalars().all()
        
        if not versions:
            logger.warning(f"No versions found for model {model_id}")
            return
        
        # Create graph for this model
        graph = nx.DiGraph()
        version_map = {}
        
        # Add vertices (versions)
        for version in versions:
            graph.add_node(version.id)
            version_map[version.id] = {
                'id': version.id,
                'version_string': version.version_string,
                'normalized_version': version.normalized_version,
                'eol_status': version.eol_status,
                'eol_date': version.eol_date,
            }
        
        # Add edges from upgrade_paths table
        result = await db.execute(
            select(UpgradePath)
            .where(UpgradePath.model_id == model_id)
        )
        upgrade_paths = result.scalars().all()
        
        for path in upgrade_paths:
            # Add edge with attributes
            graph.add_edge(
                path.from_version_id,
                path.to_version_id,
                path_id=path.id,
                mandatory_intermediates=path.mandatory_intermediate_version_ids or [],
                risk_level=path.risk_level or 'LOW',
                notes=path.notes,
                estimated_downtime_minutes=path.estimated_downtime_minutes,
                requires_backup=path.requires_backup,
                requires_reboot=path.requires_reboot
            )
        
        # Also add edges from compatibility table
        result = await db.execute(
            select(ModelVersionCompatibility)
            .where(
                ModelVersionCompatibility.model_id == model_id,
                ModelVersionCompatibility.allowed == True
            )
        )
        compatibilities = result.scalars().all()
        
        for compat in compatibilities:
            # Only add if not already present from upgrade_paths
            if not graph.has_edge(compat.from_version_id, compat.to_version_id):
                graph.add_edge(
                    compat.from_version_id,
                    compat.to_version_id,
                    compatibility_id=compat.id,
                    risk_level='LOW',
                    notes=compat.notes,
                    requires_backup=True,
                    requires_reboot=True
                )
        
        self.model_graphs[model_id] = graph
        self.version_map.update(version_map)
        
        logger.info(
            f"Built graph for model {model_id}: "
            f"{graph.number_of_nodes()} versions, {graph.number_of_edges()} paths"
        )
    
    def find_upgrade_path(
        self,
        model_id: int,
        from_version_id: int,
        to_version_id: int
    ) -> Optional[List[Tuple[int, int]]]:
        """
        Find shortest valid upgrade path from one version to another.
        
        Args:
            model_id: Model ID
            from_version_id: Starting version ID
            to_version_id: Target version ID
            
        Returns:
            List of (from_id, to_id) tuples representing the path, or None if no path exists
        """
        if model_id not in self.model_graphs:
            logger.warning(f"No graph available for model {model_id}")
            return None
        
        graph = self.model_graphs[model_id]
        
        if from_version_id not in graph or to_version_id not in graph:
            logger.warning(f"Version not found in graph: {from_version_id} or {to_version_id}")
            return None
        
        try:
            # Find shortest path using BFS (unweighted)
            path_nodes = nx.shortest_path(graph, from_version_id, to_version_id)
            
            # Convert to list of edges
            path_edges = []
            for i in range(len(path_nodes) - 1):
                path_edges.append((path_nodes[i], path_nodes[i + 1]))
            
            return path_edges
        
        except nx.NetworkXNoPath:
            logger.warning(f"No path found from {from_version_id} to {to_version_id}")
            return None
    
    def expand_path_with_intermediates(
        self,
        model_id: int,
        path_edges: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """
        Expand path to include mandatory intermediate steps.
        
        Args:
            model_id: Model ID
            path_edges: List of (from_id, to_id) tuples
            
        Returns:
            Expanded path with mandatory intermediates inserted
        """
        if model_id not in self.model_graphs:
            return path_edges
        
        graph = self.model_graphs[model_id]
        expanded = []
        
        for from_id, to_id in path_edges:
            # Check if this edge has mandatory intermediates
            edge_data = graph.get_edge_data(from_id, to_id)
            if not edge_data:
                expanded.append((from_id, to_id))
                continue
            
            mandatory_intermediates = edge_data.get('mandatory_intermediates', [])
            
            if not mandatory_intermediates:
                expanded.append((from_id, to_id))
            else:
                # Insert intermediates
                current = from_id
                for intermediate_id in mandatory_intermediates:
                    expanded.append((current, intermediate_id))
                    current = intermediate_id
                expanded.append((current, to_id))
        
        return expanded
    
    def get_path_details(
        self,
        model_id: int,
        path_edges: List[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """
        Get detailed information for each step in the path.
        
        Args:
            model_id: Model ID
            path_edges: List of (from_id, to_id) tuples
            
        Returns:
            List of step dictionaries with details
        """
        if model_id not in self.model_graphs:
            return []
        
        graph = self.model_graphs[model_id]
        steps = []
        
        for from_id, to_id in path_edges:
            from_version = self.version_map.get(from_id, {})
            to_version = self.version_map.get(to_id, {})
            edge_data = graph.get_edge_data(from_id, to_id) or {}
            
            step = {
                'from_version_id': from_id,
                'to_version_id': to_id,
                'from_version': from_version.get('version_string'),
                'to_version': to_version.get('version_string'),
                'risk_level': edge_data.get('risk_level', 'LOW'),
                'notes': edge_data.get('notes'),
                'estimated_downtime_minutes': edge_data.get('estimated_downtime_minutes'),
                'requires_backup': edge_data.get('requires_backup', True),
                'requires_reboot': edge_data.get('requires_reboot', True),
                'mandatory_intermediates': edge_data.get('mandatory_intermediates', [])
            }
            
            steps.append(step)
        
        return steps
    
    def calculate_overall_risk(self, steps: List[Dict[str, Any]]) -> str:
        """Calculate overall risk level for upgrade path"""
        risk_levels = [step['risk_level'] for step in steps]
        
        if 'HIGH' in risk_levels:
            return 'HIGH'
        elif 'MED' in risk_levels:
            return 'MED'
        else:
            return 'LOW'
    
    def calculate_total_downtime(self, steps: List[Dict[str, Any]]) -> Optional[int]:
        """Calculate total estimated downtime in minutes"""
        total = 0
        has_estimate = False
        
        for step in steps:
            downtime = step.get('estimated_downtime_minutes')
            if downtime is not None:
                total += downtime
                has_estimate = True
        
        return total if has_estimate else None
    
    async def compute_upgrade_path(
        self,
        db: AsyncSession,
        model_id: int,
        from_version_id: int,
        to_version_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Compute complete upgrade path with all details.
        
        Args:
            db: Database session
            model_id: Model ID
            from_version_id: Starting version ID
            to_version_id: Target version ID
            
        Returns:
            Dictionary with complete upgrade path details or None
        """
        # Build graph if not already built
        if model_id not in self.model_graphs:
            await self.build_graph_from_db(db, model_id)
        
        # Find base path
        path_edges = self.find_upgrade_path(model_id, from_version_id, to_version_id)
        if not path_edges:
            return None
        
        # Expand with mandatory intermediates
        expanded_path = self.expand_path_with_intermediates(model_id, path_edges)
        
        # Get step details
        steps = self.get_path_details(model_id, expanded_path)
        
        # Calculate overall metrics
        overall_risk = self.calculate_overall_risk(steps)
        total_downtime = self.calculate_total_downtime(steps)
        
        return {
            'model_id': model_id,
            'from_version_id': from_version_id,
            'to_version_id': to_version_id,
            'steps': steps,
            'overall_risk': overall_risk,
            'total_estimated_downtime_minutes': total_downtime,
            'step_count': len(steps)
        }
    
    def validate_path(
        self,
        model_id: int,
        from_version_id: int,
        to_version_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if an upgrade path exists and is safe.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if model_id not in self.model_graphs:
            return False, f"No graph available for model {model_id}"
        
        graph = self.model_graphs[model_id]
        
        if from_version_id not in graph:
            return False, f"Source version {from_version_id} not found"
        
        if to_version_id not in graph:
            return False, f"Target version {to_version_id} not found"
        
        # Check if path exists
        if not nx.has_path(graph, from_version_id, to_version_id):
            return False, f"No upgrade path exists from version {from_version_id} to {to_version_id}"
        
        return True, None
