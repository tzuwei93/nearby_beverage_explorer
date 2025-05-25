"""Version management module for deployments"""

import os
import tomlkit

class VersionManager:
    """Handles version generation and management for deployments"""
    
    @staticmethod
    def generate_version():
        """
        Read version from pyproject.toml file
        
        Returns:
            str: The version string prefixed with 'v' (e.g., 'v0.1.0')
        
        Raises:
            FileNotFoundError: If pyproject.toml cannot be found
            KeyError: If version information is missing in pyproject.toml
        """
        # Find the project root directory (where pyproject.toml is located)
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pyproject_path = os.path.join(current_dir, 'pyproject.toml')
        
        # Read and parse the TOML file
        with open(pyproject_path, 'r', encoding='utf-8') as f:
            pyproject_data = tomlkit.parse(f.read())
        
        # Extract the version
        version = pyproject_data['tool']['poetry']['version']
        
        # Return the version with 'v' prefix
        return f'v{version}'