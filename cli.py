# cli.py
import typer

app = typer.Typer(add_completion=False)


@app.command()
def dev(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
):
    """
    Start the FastAPI dev server (like `npm run dev`).
    """
    import uvicorn
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)



if __name__ == "__main__":
    app()
