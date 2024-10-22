import json
import asyncio
from tqdm import tqdm

import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

from pipeline.utils import prompts, upload_to_gemini, wait_for_files_active

MODEL_NAME = "gemini-1.5-flash-8b"

def ask_gemini_for_double_check(figure_path):
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_schema": content.Schema(
            type = content.Type.OBJECT,
            required = ["response"],
            properties = {
                "response": content.Schema(
                    type = content.Type.BOOLEAN,
                ),
            },
        ),
        "response_mime_type": "application/json",
    }

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config=generation_config,
    )

    files = [
        upload_to_gemini(figure_path, mime_type="image/png"),
    ]
    wait_for_files_active(files)

    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    files[0],
                ],
            },
        ]
    )

    prompt = prompts["double_check_figure"]["prompt"]
    response = chat_session.send_message(prompt)
    return response.text

def double_check_figure(figure_path):
    include_figure = ask_gemini_for_double_check(figure_path)
    include_figure = json.loads(include_figure)["response"]
    return include_figure

async def process_figure_double_check(figure_path, pbar):
    figure_included = double_check_figure(figure_path)
    pbar.update(1)
    if figure_included:
        return figure_path
    else:
        return None

async def doublecheck_figures(figure_paths, workers):
    double_checking_tasks = []
    double_checking_results = []

    semaphore = asyncio.Semaphore(workers)
    with tqdm(total=len(figure_paths)) as pbar:
        async def worker(figure_path):
            async with semaphore:
                return await process_figure_double_check(figure_path, pbar)

        double_checking_tasks = [worker(figure_path) for figure_path in figure_paths]
        results = await asyncio.gather(*double_checking_tasks)
        for result in results:
            if result is not None:
                double_checking_results.append(result)

    return double_checking_results