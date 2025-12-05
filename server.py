from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from agent.functions import AgentFunstions
from scrape import ScarapeANDSave

app = FastAPI(title="AI Estimator", version="0.0.1")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create an instance of the AgentFunstions class
agent_functions = AgentFunstions()
scrape_and_save = ScarapeANDSave()

@app.get("/")
async def root():
    return {"Server": "Running"}

# show the UI
@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    try:
        with open("front/front.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: HTML file not found.</h1>"

# User query
@app.post("/query")
async def query(user_input: str):
    try:
        agent_process_response = await agent_functions.query_process(user_input)
        if agent_process_response["status"] != 0:
            return {"status": -1, "message": agent_process_response["message"], "data": {}}
        
        return {"status": 0, "message": "", "data": agent_process_response["data"]}
    except Exception as e:
        return {"status": -1, "message": str(e), "data": {}}
    

@app.post("/query/stream")
async def query_stream(user_input: str):
    try:
        generator = agent_functions.query_process_stream(user_input)
        return StreamingResponse(generator, media_type="application/x-ndjson")
    except Exception as e:
        return {"status": -1, "message": str(e), "data": {}}
    

# Scrape endpoint
@app.post("/scrape")
async def scrape(url: str):
    try:
        fetch_url_res = await scrape_and_save.fetch_url(url)
        if fetch_url_res['status'] != 0:
            raise Exception(fetch_url_res['meassage'])

        soup = fetch_url_res['data']

        extract_semantic_chunks_res = await scrape_and_save.extract_semantic_chunks(soup, url)
        if extract_semantic_chunks_res['status'] != 0:
            raise Exception(extract_semantic_chunks_res['message'])

        ids = extract_semantic_chunks_res['data']['ids']
        docs = extract_semantic_chunks_res['data']['docs']
        metas = extract_semantic_chunks_res['data']['metas']

        save_chunks_res = await scrape_and_save.save_chunks(ids=ids, docs=docs, metas=metas)
        if save_chunks_res['status'] != 0:
            raise Exception(save_chunks_res['message'])

        return {"status": 0, "message": "", "data": {"len": len(ids)}}
    except Exception as e:
        return {"status": -1, "message": str(e), "data": {}}




if __name__ == "__main__":
    import uvicorn
    # Get the frontend UI at "http://localhost:8000/ui" endpint
    uvicorn.run(app, host="0.0.0.0", port=8000)