
import ray
import os
import glob
from pathlib import Path

def search_node():
    # Places to look
    search_roots = [
        os.path.expanduser("~"),
        str(Path("C:/Users")),
        "/home",
        "/data",
        "/tmp"
    ]
    
    matches = []
    patterns = ["**/fr_wheat_feat_*.tif", "**/index.csv", "**/patch_*.npz"]
    
    for root in search_roots:
        if not os.path.exists(root):
            continue
            
        try:
            # Walk avoids permission errors better than globbing root directly sometimes
            for current_root, dirs, files in os.walk(root):
                # Skip massive system dirs to save time
                if "Windows" in current_root or "Program Files" in current_root or "AppData" in current_root or ".git" in current_root:
                    continue
                    
                for file in files:
                    if file.startswith("fr_wheat_feat_") and file.endswith(".tif"):
                        matches.append(os.path.join(current_root, file))
                    elif file == "index.csv":
                         # Check if it looks like our index
                         matches.append(os.path.join(current_root, file))
                    elif file.startswith("patch_") and file.endswith(".npz"):
                         matches.append(os.path.join(current_root, file))
                         
                # Limit depth/breadth if needed, but for now we just scan
                # Stop if we found a lot
                if len(matches) > 10:
                    break
            if len(matches) > 10:
                break
        except Exception:
            pass
            
    return {
        "node_ip": ray.util.get_node_ip_address(),
        "hostname": os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "unknown")),
        "matches": matches[:10]
    }

if __name__ == "__main__":
    ray.init(address="auto")
    
    # Run on all nodes
    resources = ray.available_resources()
    # Logic to run on every node is tricky without exact resource keys, 
    # but we can try to schedule many tasks
    
    # Better strategy: Get all node IDs
    nodes = ray.nodes()
    node_ids = [n["NodeID"] for n in nodes if n["Alive"]]
    
    print(f"Searching on {len(node_ids)} nodes...")
    
    @ray.remote
    def run_search():
        return search_node()
    
    # We want to force one task per node. 
    # We can use resource constraints if we knew them, 
    # or just launch N tasks where N = num_cpus and hope they spread, 
    # or use the specific 'node:<ip>' resource if available.
    
    tasks = []
    for n in nodes:
        if not n["Alive"]: continue
        # Each node has a resource like 'node:192.168.x.x': 1.0
        node_ip = n["NodeManagerAddress"]
        res_key = f"node:{node_ip}"
        
        # Schedule specifically on this node
        tasks.append(run_search.options(resources={res_key: 0.01}).remote())
        
    results = ray.get(tasks)
    
    found_any = False
    for r in results:
        if r["matches"]:
            found_any = True
            print(f"\n--- Node: {r['node_ip']} ({r['hostname']}) ---")
            for m in r["matches"]:
                print(f"  FOUND: {m}")
                
    if not found_any:
        print("\nNo matching files found on any node.")
