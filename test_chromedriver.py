"""
Test script to verify ChromeDriver setup
"""

def test_chromedriver_setup():
    """Test if ChromeDriver can be set up correctly"""
    
    print("Testing ChromeDriver Setup...")
    print("=" * 40)
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        print("✓ All packages imported successfully")
        
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        print("✓ Chrome options configured")
        
        # Try to get ChromeDriver automatically
        print("Downloading/updating ChromeDriver...")
        service = Service(ChromeDriverManager().install())
        print("✓ ChromeDriver downloaded successfully")
        
        # Try to start the driver
        print("Starting Chrome driver...")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✓ Chrome driver started successfully")
        
        # Test basic functionality
        print("Testing basic functionality...")
        driver.get("https://www.google.com")
        title = driver.title
        print(f"✓ Successfully loaded page: {title}")
        
        # Clean up
        driver.quit()
        print("✓ Driver closed successfully")
        
        print("\n" + "=" * 40)
        print("✅ ALL TESTS PASSED!")
        print("ChromeDriver is working correctly")
        return True
        
    except ImportError as e:
        print(f"✗ Package import error: {e}")
        print("Install missing packages with: pip install selenium webdriver-manager")
        return False
        
    except Exception as e:
        print(f"✗ ChromeDriver error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Google Chrome browser is installed")
        print("2. Remove old chromedriver: sudo rm /usr/local/bin/chromedriver")
        print("3. Clear cache: rm -rf ~/.wdm")
        return False

def check_system_info():
    """Check system information for debugging"""
    
    print("\nSystem Information:")
    print("=" * 30)
    
    import platform
    import subprocess
    
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    
    try:
        # Check Chrome version
        result = subprocess.run([
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', 
            '--version'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print(f"Chrome: {result.stdout.strip()}")
        else:
            print("Chrome: Not found or error")
            
    except Exception:
        print("Chrome: Could not detect version")
    
    # Check existing chromedriver
    try:
        result = subprocess.run(['chromedriver', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"Existing ChromeDriver: {result.stdout.strip()}")
        else:
            print("Existing ChromeDriver: None found")
    except Exception:
        print("Existing ChromeDriver: None in PATH")

if __name__ == "__main__":
    check_system_info()
    test_chromedriver_setup()