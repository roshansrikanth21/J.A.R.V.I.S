import yaml
import sys
import os
from jarvis.engine import JarvisEngine

def main():
    print("=======================================")
    print("      J.A.R.V.I.S. BOOT SEQUENCE     ")
    print("=======================================")
    
    # Load config
    if not os.path.exists("config.yaml"):
        print("[ERROR] config.yaml not found!")
        sys.exit(1)
        
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    engine = JarvisEngine(config)
    
    try:
        engine.run()
    except KeyboardInterrupt:
        print("\n[JARVIS] Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()
