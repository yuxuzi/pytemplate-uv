import typer
import subprocess

def main( app :str=None):
  
    match(app):
        case "fastapi":
            template="fastapi_template"            
            
        case _:
            template="pyproject_template"
            
    subprocess.run(["cookiecutter", f"templates/{template}"])  
        
    
if __name__ == "__main__":
    typer.run(main)
