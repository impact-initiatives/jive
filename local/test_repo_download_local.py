import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from jira_client import JiraClient

def main():
    print("Initializing JiraClient and loading credentials...")
    client = JiraClient()
    
    url = "https://repository.impact-initiatives.org/resources/view-resource/?id=66050"
    print(f"Target URL: {url}")
    
    try:
        print("\n[Step 1] Creating authenticated WordPress session...")
        session = client._get_repo_session()
        print("  WordPress session created successfully!")
        
        print("\n[Step 2] Scraping page for direct Excel link...")
        excel_url = client._scrape_excel_url(url)
        print(f"  Scraped direct Excel URL: {excel_url}")
        
        if not excel_url:
            print("  [Error] Direct Excel URL not found on the page!")
            return
            
        dest_dir = project_root / "output"
        dest_dir.mkdir(exist_ok=True)
        filename = excel_url.split("/")[-1]
        dest_path = dest_dir / filename
        
        print(f"\n[Step 3] Downloading Excel to: {dest_path.relative_to(project_root)}...")
        success = client._download_file_with_retry(excel_url, dest_path, session=session)
        
        if success and dest_path.exists():
            size_kb = dest_path.stat().st_size / 1024
            print("\nDownload test SUCCESS!")
            print(f"  File downloaded: {dest_path.name}")
            print(f"  Size           : {size_kb:.2f} KB")
        else:
            print("\nDownload test failed to save file.")
            
    except Exception as e:
        print(f"\nDownload test encountered an error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

