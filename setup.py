"""
Setup script for the Critical Call Analysis application
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages from requirements.txt"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def create_env_file():
    """Create .env file if it doesn't exist"""
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("# AssemblyAI API Key\n")
            f.write("# Get your free API key at https://www.assemblyai.com/\n")
            f.write("ASSEMBLYAI_API_KEY=your_api_key_here\n")
        print("✅ Created .env file template")
        print("📝 Please edit .env and add your AssemblyAI API key")
    else:
        print("✅ .env file already exists")

def run_setup():
    """Run the complete setup process"""
    print("🚀 Setting up Critical Call Analysis Application\n")
    
    # Check Python version
    if not check_python_version():
        return
    
    # Install requirements
    if not install_requirements():
        return
    
    # Create env file
    create_env_file()
    
    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Edit .env file and add your AssemblyAI API key")
    print("2. Run: streamlit run app.py")
    print("3. Open http://localhost:8501 in your browser")
    print("\n💡 Get your free AssemblyAI API key at: https://www.assemblyai.com/")

if __name__ == "__main__":
    run_setup()