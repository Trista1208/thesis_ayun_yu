#!/usr/bin/env python3
"""
Visualize Mutual Information Relationships

Creates graphs showing mutual information relationships between sections.

USAGE:
    # Option 1: Activate venv first
    source venv/bin/activate
    python visualize_mutual_information.py

    # Option 2: Use venv Python directly (no activation needed)
    venv/bin/python visualize_mutual_information.py
"""

import json
import glob
import os
import sys
from pathlib import Path

# Check if we're likely using the venv BEFORE any heavy imports
def check_venv():
    """Check if we're using the virtual environment."""
    venv_path = os.path.join(os.path.dirname(__file__), 'venv')
    if os.path.exists(venv_path):
        python_path = sys.executable
        if 'venv' not in python_path and 'VIRTUAL_ENV' not in os.environ:
            print("=" * 70)
            print("WARNING: You may not be using the virtual environment!")
            print("=" * 70)
            print(f"Current Python: {python_path}")
            print("\nTo use the virtual environment:")
            print("  source venv/bin/activate")
            print("  python visualize_mutual_information.py")
            print("\nOr use venv Python directly:")
            print("  venv/bin/python visualize_mutual_information.py")
            print("\nOr use the helper script:")
            print("  ./run_visualization.sh")
            print("\nContinuing anyway...")
            print()

# Early check before imports - warn but don't exit (in case user wants to proceed)
check_venv()

try:
    import numpy as np
    import pandas as pd
except ImportError as e:
    print("=" * 70)
    print("ERROR: Failed to import required packages!")
    print("=" * 70)
    print(f"Error: {e}")
    check_venv()
    print("\nPlease ensure you're using the virtual environment.")
    import sys
    sys.exit(1)
except ValueError as e:
    if "numpy.dtype size changed" in str(e) or "binary incompatibility" in str(e):
        print("=" * 70)
        print("ERROR: Binary incompatibility detected during import!")
        print("=" * 70)
        print("This error occurs when using system Python instead of the virtual environment.")
        print(f"\nCurrent Python: {sys.executable}")
        print("\nSOLUTION: Use the virtual environment Python:")
        print("  source venv/bin/activate")
        print("  python visualize_mutual_information.py")
        print("\nOr use venv Python directly:")
        print("  venv/bin/python visualize_mutual_information.py")
        print("\nOr use the helper script:")
        print("  ./run_visualization.sh")
        print("\nIf using an IDE (VS Code, PyCharm, etc.):")
        print("  Configure it to use: " + os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'python'))
        import sys
        sys.exit(1)
    else:
        raise

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import seaborn as sns
    from matplotlib.patches import FancyBboxPatch
except ImportError as e:
    print("=" * 70)
    print("ERROR: Missing required packages!")
    print("=" * 70)
    print(f"Error: {e}")
    print("\nPlease install matplotlib and seaborn using the virtual environment:")
    print("  source venv/bin/activate")
    print("  pip install matplotlib seaborn")
    print("\nOr use the venv Python directly:")
    print("  venv/bin/python visualize_mutual_information.py")
    import sys
    sys.exit(1)
except ValueError as e:
    if "numpy.dtype size changed" in str(e) or "binary incompatibility" in str(e):
        print("=" * 70)
        print("ERROR: Binary incompatibility detected!")
        print("=" * 70)
        print("This error indicates you're using system Python instead of the virtual environment.")
        print("\nSOLUTION: Use the virtual environment Python:")
        print("  source venv/bin/activate")
        print("  python visualize_mutual_information.py")
        print("\nOr use venv Python directly:")
        print("  venv/bin/python visualize_mutual_information.py")
        import sys
        sys.exit(1)
    else:
        raise


def find_latest_analysis_file():
    """Find the most recent analysis JSON file."""
    # Check in output directory first, then fallback to root
    output_dir = "output"
    json_files = glob.glob(os.path.join(output_dir, "schema_relationship_analysis_*.json"))
    if not json_files:
        json_files = glob.glob("schema_relationship_analysis_*.json")
    if not json_files:
        return None
    
    # Sort by modification time
    json_files.sort(key=os.path.getmtime, reverse=True)
    return json_files[0]


def load_mutual_information_data(json_file, exclude_sections=None):
    """Load mutual information data from JSON file, optionally excluding certain sections."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    mi_data = data.get('mutual_information', {})
    
    # Filter out excluded sections if specified
    if exclude_sections:
        filtered_mi_data = {}
        for section_pair, pairs in mi_data.items():
            # Check if any excluded section is in the pair
            skip = False
            for excluded in exclude_sections:
                if excluded in section_pair:
                    skip = True
                    break
            
            if not skip:
                # Also filter individual relationships
                filtered_pairs = []
                for pair in pairs:
                    skip_pair = False
                    for excluded in exclude_sections:
                        if excluded in pair.get('section1', '') or excluded in pair.get('section2', ''):
                            skip_pair = True
                            break
                    if not skip_pair:
                        filtered_pairs.append(pair)
                
                if filtered_pairs:  # Only add if there are remaining pairs
                    filtered_mi_data[section_pair] = filtered_pairs
        
        return filtered_mi_data
    
    return mi_data


def create_section_mi_matrix(mi_data):
    """Create a matrix of mutual information between sections."""
    # Extract all unique sections
    sections = set()
    for section_pair, pairs in mi_data.items():
        for pair in pairs:
            sections.add(pair['section1'])
            sections.add(pair['section2'])
    
    sections = sorted(list(sections))
    n_sections = len(sections)
    
    # Create matrix
    mi_matrix = np.zeros((n_sections, n_sections))
    section_to_idx = {sec: i for i, sec in enumerate(sections)}
    
    # Fill matrix with average MI between sections
    for section_pair, pairs in mi_data.items():
        if not pairs:
            continue
        
        # Extract section names from pair string
        parts = section_pair.split(' vs ')
        if len(parts) == 2:
            sec1, sec2 = parts[0], parts[1]
            if sec1 in section_to_idx and sec2 in section_to_idx:
                # Calculate average MI for this pair
                avg_mi = np.mean([p['mutual_information'] for p in pairs])
                idx1 = section_to_idx[sec1]
                idx2 = section_to_idx[sec2]
                mi_matrix[idx1, idx2] = avg_mi
                mi_matrix[idx2, idx1] = avg_mi  # Make symmetric
    
    return mi_matrix, sections


def create_network_graph(mi_data, output_file):
    """Create a network graph showing MI relationships."""
    # Prepare data for network
    edges = []
    for section_pair, pairs in mi_data.items():
        if not pairs:
            continue
        
        parts = section_pair.split(' vs ')
        if len(parts) == 2:
            sec1, sec2 = parts[0], parts[1]
            # Get max MI for this section pair
            max_mi = max([p['mutual_information'] for p in pairs])
            avg_mi = np.mean([p['mutual_information'] for p in pairs])
            edges.append({
                'source': sec1,
                'target': sec2,
                'max_mi': max_mi,
                'avg_mi': avg_mi,
                'num_relationships': len(pairs)
            })
    
    if not edges:
        print("No mutual information data to visualize")
        return
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Get unique sections
    all_sections = set()
    for edge in edges:
        all_sections.add(edge['source'])
        all_sections.add(edge['target'])
    sections = sorted(list(all_sections))
    
    # Create positions using a circular layout
    n = len(sections)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    radius = 1.5
    x_pos = radius * np.cos(angles)
    y_pos = radius * np.sin(angles)
    
    pos = {sec: (x_pos[i], y_pos[i]) for i, sec in enumerate(sections)}
    
    # Draw edges
    max_mi_value = max([e['avg_mi'] for e in edges])
    min_mi_value = min([e['avg_mi'] for e in edges])
    mi_range = max_mi_value - min_mi_value if max_mi_value != min_mi_value else 1
    
    for edge in edges:
        x1, y1 = pos[edge['source']]
        x2, y2 = pos[edge['target']]
        
        # Normalize MI for line width and color
        normalized_mi = (edge['avg_mi'] - min_mi_value) / mi_range
        line_width = 1 + normalized_mi * 4  # Line width 1-5
        alpha = 0.3 + normalized_mi * 0.7  # Alpha 0.3-1.0
        
        ax.plot([x1, x2], [y1, y2], 
                linewidth=line_width, 
                alpha=alpha,
                color='steelblue',
                zorder=1)
    
    # Draw nodes (sections)
    for i, section in enumerate(sections):
        x, y = pos[section]
        ax.scatter(x, y, s=500, c='lightcoral', edgecolors='black', 
                  linewidths=2, zorder=2)
        
        # Add section labels
        ax.text(x, y, section.replace(' ', '\n'), 
               ha='center', va='center', fontsize=8, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))
    
    # Add title and legend
    ax.set_title('Mutual Information Network Between Sections\n' +
                f'(Line thickness and opacity indicate MI strength, {len(edges)} relationships)',
                fontsize=14, fontweight='bold', pad=20)
    ax.axis('off')
    ax.set_aspect('equal')
    
    # Add legend for line width
    legend_elements = [
        plt.Line2D([0], [0], color='steelblue', linewidth=1, alpha=0.3, label='Low MI'),
        plt.Line2D([0], [0], color='steelblue', linewidth=3, alpha=0.7, label='Medium MI'),
        plt.Line2D([0], [0], color='steelblue', linewidth=5, alpha=1.0, label='High MI')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Network graph saved to: {output_file}")
    plt.close()


def create_heatmap(mi_data, output_file):
    """Create a heatmap of mutual information between sections."""
    mi_matrix, sections = create_section_mi_matrix(mi_data)
    
    if mi_matrix.sum() == 0:
        print("No mutual information data to visualize")
        return
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Create heatmap
    sns.heatmap(mi_matrix, 
                xticklabels=sections,
                yticklabels=sections,
                annot=True, 
                fmt='.3f',
                cmap='YlOrRd',
                cbar_kws={'label': 'Average Mutual Information'},
                square=True,
                linewidths=0.5,
                ax=ax)
    
    ax.set_title('Mutual Information Heatmap Between Sections', 
                fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Section', fontsize=12)
    ax.set_ylabel('Section', fontsize=12)
    
    # Rotate labels
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Heatmap saved to: {output_file}")
    plt.close()


def create_top_relationships_bar(mi_data, output_file, top_n=30, min_observations=10):
    """Create a bar chart of top mutual information relationships."""
    # Collect all relationships
    all_relationships = []
    for section_pair, pairs in mi_data.items():
        for pair in pairs:
            # Optionally filter by minimum observations if field exists
            if 'n_observations' in pair and pair['n_observations'] < min_observations:
                continue
            
            all_relationships.append({
                'var1': pair['var1'],
                'var2': pair['var2'],
                'mi': pair['mutual_information'],
                'n_obs': pair.get('n_observations', None),
                'section_pair': section_pair
            })
    
    if not all_relationships:
        print("No mutual information data to visualize")
        return
    
    # Sort by MI and take top N
    all_relationships.sort(key=lambda x: x['mi'], reverse=True)
    top_relationships = all_relationships[:top_n]
    
    # Create better labels - wrap long names intelligently
    def format_label(var_name, max_len=35):
        """Format variable name with smart wrapping."""
        if len(var_name) <= max_len:
            return var_name
        # Try to break at word boundaries
        words = var_name.split()
        if len(words) > 1:
            # Try to split into two lines
            mid = len(words) // 2
            line1 = ' '.join(words[:mid])
            line2 = ' '.join(words[mid:])
            if len(line1) <= max_len and len(line2) <= max_len:
                return f"{line1}\n{line2}"
        # Fallback: truncate with ellipsis
        return var_name[:max_len-3] + "..."
    
    mi_values = [r['mi'] for r in top_relationships]
    
    # Create figure - wider to accommodate labels on the right
    fig, ax = plt.subplots(figsize=(18, max(10, top_n * 0.4)))
    
    # Create horizontal bar chart with more spacing
    y_pos = np.arange(len(top_relationships))
    bars = ax.barh(y_pos, mi_values, color='steelblue', alpha=0.7, edgecolor='black', height=0.8)
    
    # Get max MI value for positioning labels
    max_mi = max(mi_values)
    
    # Add relationship labels on the RIGHT side of each bar
    for i, (bar, rel, val) in enumerate(zip(bars, top_relationships, mi_values)):
        # Position label to the right of the bar
        x_pos = max_mi * 1.15  # Position to the right of the longest bar
        
        # Format variable names (truncate if too long, but show more)
        var1 = rel['var1']
        var2 = rel['var2']
        max_var_len = 40
        
        if len(var1) > max_var_len:
            var1 = var1[:max_var_len-3] + "..."
        if len(var2) > max_var_len:
            var2 = var2[:max_var_len-3] + "..."
        
        # Create label text
        label_text = f"{var1} ↔ {var2}"
        
        # Add label on the right
        ax.text(x_pos, bar.get_y() + bar.get_height()/2, 
               label_text,
               ha='left', va='center', fontsize=10, 
               bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.7, edgecolor='gray'))
        
        # Add MI value label inside or on the bar
        width = bar.get_width()
        mi_label = f'{val:.4f}'
        # Add observation count if available
        if rel.get('n_obs') is not None:
            mi_label += f'\n(n={rel["n_obs"]})'
        ax.text(width + width*0.01, bar.get_y() + bar.get_height()/2, 
               mi_label, 
               ha='left', va='center', fontsize=9, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    
    # Use simple numeric labels on y-axis
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"#{i+1}" for i in range(len(top_relationships))], fontsize=9)
    ax.set_xlabel('Mutual Information', fontsize=13, fontweight='bold')
    ax.set_title(f'Top {top_n} Mutual Information Relationships', 
                fontsize=15, fontweight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Adjust layout - leave space on right for labels
    plt.subplots_adjust(left=0.08, right=0.65, top=0.95, bottom=0.1)
    plt.savefig(output_file, dpi=300, bbox_inches='tight', pad_inches=0.2)
    print(f"Top relationships bar chart saved to: {output_file}")
    plt.close()


def create_variable_summary(mi_data, output_file, min_mi=0.1, top_n_vars=20, top_connections=None, min_observations=10):
    """Create a summary visualization showing which variables have MI with each variable."""
    # Build a dictionary: variable -> list of (other_variable, mi_value, n_obs, section_pair)
    variable_connections = {}
    
    for section_pair, pairs in mi_data.items():
        for pair in pairs:
            var1 = pair['var1']
            var2 = pair['var2']
            mi_val = pair['mutual_information']
            
            if mi_val < min_mi:
                continue
            
            # Optionally filter by minimum observations
            if 'n_observations' in pair and pair['n_observations'] < min_observations:
                continue
            
            n_obs = pair.get('n_observations', None)
            
            # Add var2 to var1's connections
            if var1 not in variable_connections:
                variable_connections[var1] = []
            variable_connections[var1].append((var2, mi_val, n_obs, section_pair))
            
            # Add var1 to var2's connections (symmetric)
            if var2 not in variable_connections:
                variable_connections[var2] = []
            variable_connections[var2].append((var1, mi_val, n_obs, section_pair))
    
    # Sort variables by number of connections (most connected first)
    sorted_vars = sorted(variable_connections.items(), 
                        key=lambda x: len(x[1]), reverse=True)
    
    # Take top variables with most connections
    top_vars = sorted_vars[:top_n_vars]
    
    if not top_vars:
        print("No variables with sufficient mutual information relationships")
        return
    
    # Create figure with two columns
    fig = plt.figure(figsize=(22, max(14, len(top_vars) * 0.6)))
    
    # Calculate positions - leave space at top for title
    rows_per_col = (len(top_vars) + 1) // 2
    current_y = 0.92  # Start lower to leave more space for title
    
    # Left column
    for i, (var, connections) in enumerate(top_vars[:rows_per_col]):
        if i >= rows_per_col:
            break
            
        # Sort connections by MI value
        connections_sorted = sorted(connections, key=lambda x: x[1], reverse=True)
        # Show all connections if top_connections is None, otherwise limit
        if top_connections is None:
            top_conns_list = connections_sorted
        else:
            top_conns_list = connections_sorted[:top_connections]
        
        # Variable name (truncate if needed)
        var_display = var[:50] + "..." if len(var) > 50 else var
        var_label = f"{var_display}\n({len(connections)} connections)"
        
        # Create text box for variable
        fig.text(0.02, current_y, var_label,
                ha='left', va='top', fontsize=10, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7, edgecolor='black'))
        
        # Create connections list
        conn_texts = []
        for conn_data in top_conns_list:
            if len(conn_data) == 4:  # New format with n_obs
                other_var, mi_val, n_obs, section_pair = conn_data
                other_var_short = other_var[:42] + "..." if len(other_var) > 42 else other_var
                if n_obs is not None:
                    conn_texts.append(f"  → {other_var_short} (MI: {mi_val:.3f}, n={n_obs})")
                else:
                    conn_texts.append(f"  → {other_var_short} (MI: {mi_val:.3f})")
            else:  # Backward compatibility
                other_var, mi_val, section_pair = conn_data[:3]
                other_var_short = other_var[:42] + "..." if len(other_var) > 42 else other_var
                conn_texts.append(f"  → {other_var_short} (MI: {mi_val:.3f})")
        
        # Only show "... and X more" if we're limiting connections
        if top_connections is not None and len(connections) > top_connections:
            conn_texts.append(f"  ... and {len(connections) - top_connections} more")
        
        connections_str = "\n".join(conn_texts)
        
        fig.text(0.02, current_y - 0.08, connections_str,
                ha='left', va='top', fontsize=8.5,
                family='monospace',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='lightblue', alpha=0.4, edgecolor='gray'))
        
        # Calculate next position based on content
        content_height = 0.08 + (len(top_conns_list) + 1) * 0.015
        current_y -= content_height + 0.02
    
    # Right column
    current_y = 0.92  # Start lower to leave more space for title
    for i, (var, connections) in enumerate(top_vars[rows_per_col:]):
        # Sort connections by MI value
        connections_sorted = sorted(connections, key=lambda x: x[1], reverse=True)
        # Show all connections if top_connections is None, otherwise limit
        if top_connections is None:
            top_conns_list = connections_sorted
        else:
            top_conns_list = connections_sorted[:top_connections]
        
        # Variable name (truncate if needed)
        var_display = var[:50] + "..." if len(var) > 50 else var
        var_label = f"{var_display}\n({len(connections)} connections)"
        
        # Create text box for variable
        fig.text(0.52, current_y, var_label,
                ha='left', va='top', fontsize=10, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7, edgecolor='black'))
        
        # Create connections list
        conn_texts = []
        for conn_data in top_conns_list:
            if len(conn_data) == 4:  # New format with n_obs
                other_var, mi_val, n_obs, section_pair = conn_data
                other_var_short = other_var[:42] + "..." if len(other_var) > 42 else other_var
                if n_obs is not None:
                    conn_texts.append(f"  → {other_var_short} (MI: {mi_val:.3f}, n={n_obs})")
                else:
                    conn_texts.append(f"  → {other_var_short} (MI: {mi_val:.3f})")
            else:  # Backward compatibility
                other_var, mi_val, section_pair = conn_data[:3]
                other_var_short = other_var[:42] + "..." if len(other_var) > 42 else other_var
                conn_texts.append(f"  → {other_var_short} (MI: {mi_val:.3f})")
        
        # Only show "... and X more" if we're limiting connections
        if top_connections is not None and len(connections) > top_connections:
            conn_texts.append(f"  ... and {len(connections) - top_connections} more")
        
        connections_str = "\n".join(conn_texts)
        
        fig.text(0.52, current_y - 0.08, connections_str,
                ha='left', va='top', fontsize=8.5,
                family='monospace',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='lightblue', alpha=0.4, edgecolor='gray'))
        
        # Calculate next position
        content_height = 0.08 + (len(top_conns_list) + 1) * 0.015
        current_y -= content_height + 0.02
    
    conn_text = "all connections" if top_connections is None else f"top {top_connections} connections"
    fig.suptitle('Mutual Information Summary: Variables and Their Connections\n' +
                f'(Showing top {len(top_vars)} most connected variables, {conn_text} each)',
                fontsize=14, fontweight='bold', y=0.995, ha='center', x=0.5)
    
    # Add extra padding at top for title
    plt.savefig(output_file, dpi=300, bbox_inches='tight', pad_inches=0.6)
    print(f"Variable summary saved to: {output_file}")
    plt.close()


def main():
    """Main function to create visualizations."""
    print("=" * 80)
    print("MUTUAL INFORMATION VISUALIZATION")
    print("=" * 80)
    print()
    
    # Find latest analysis file
    json_file = find_latest_analysis_file()
    if not json_file:
        print("ERROR: No analysis JSON file found!")
        print("Please run profile_schema_analysis.py first.")
        return
    
    print(f"Loading data from: {json_file}")
    
    # Exclude demographic and retest questionnaire sections from visualizations
    exclude_sections = ['Demographic', 'Retest Questionnaire']
    print(f"Excluding sections: {', '.join(exclude_sections)}")
    
    mi_data = load_mutual_information_data(json_file, exclude_sections=exclude_sections)
    
    if not mi_data:
        print("ERROR: No mutual information data found in the analysis file!")
        return
    
    total_relationships = sum(len(pairs) for pairs in mi_data.values())
    print(f"Found {total_relationships} mutual information relationships (after filtering)")
    print()
    
    # Create output directory
    output_dir = os.path.join("output", "mutual_information_visualizations")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create visualizations
    print("Creating visualizations...")
    print()
    
    # 1. Network graph
    print("1. Creating network graph...")
    network_file = os.path.join(output_dir, "mi_network_graph.png")
    create_network_graph(mi_data, network_file)
    
    # 2. Heatmap
    print("\n2. Creating heatmap...")
    heatmap_file = os.path.join(output_dir, "mi_heatmap.png")
    create_heatmap(mi_data, heatmap_file)
    
    # 3. Top relationships bar chart
    print("\n3. Creating top relationships bar chart...")
    bar_file = os.path.join(output_dir, "mi_top_relationships.png")
    create_top_relationships_bar(mi_data, bar_file, top_n=30)
    
    # 4. Variable summary (show all connections)
    print("\n4. Creating variable summary...")
    summary_file = os.path.join(output_dir, "mi_variable_summary.png")
    create_variable_summary(mi_data, summary_file, min_mi=0.1, top_n_vars=20, top_connections=None)
    
    print("\n" + "=" * 80)
    print("✓ All visualizations created successfully!")
    print(f"  Output directory: {output_dir}/")
    print("=" * 80)


if __name__ == "__main__":
    main()

