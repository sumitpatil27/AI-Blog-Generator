

from __future__ import annotations

import operator
from typing import TypedDict, List, Annotated, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

import os
from pathlib import Path


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# HELPER FUNCTION
# ============================================================

def extract_text(content):
    """
    Convert Gemini/LangChain response content into a plain string.

    Gemini may return:
    - a normal string
    - a list of content blocks
    """

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = []

        for block in content:

            # Example: ["some text", "more text"]
            if isinstance(block, str):
                text_parts.append(block)

            # Example:
            # {"type": "text", "text": "some text"}
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

        return "\n".join(text_parts).strip()

    # Fallback
    return str(content).strip()


# ============================================================
# TASK SCHEMA
# ============================================================

class Task(BaseModel):
    id: int
    title: str

    goal: str = Field(
        ...,
        description=(
            "One sentence describing what the reader should "
            "be able to do/understand after this section."
        ),
    )

    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description=(
            "3–5 concrete, non-overlapping subpoints "
            "to cover in this section."
        ),
    )

    target_words: int = Field(
        ...,
        description="Target word count for this section (120–450).",
    )

    section_type: Literal[
        "intro",
        "core",
        "examples",
        "checklist",
        "common_mistakes",
        "conclusion",
    ] = Field(
        ...,
        description="Use 'common_mistakes' exactly once in the plan.",
    )


# ============================================================
# PLAN SCHEMA
# ============================================================

class Plan(BaseModel):
    blog_title: str

    audience: str = Field(
        ...,
        description="Who this blog is for.",
    )

    tone: str = Field(
        ...,
        description="Writing tone (e.g., practical, crisp).",
    )

    tasks: List[Task]


# ============================================================
# LANGGRAPH STATE
# ============================================================

class State(TypedDict):
    topic: str
    plan: Plan
    sections: Annotated[List[str], operator.add]
    final: str


# ============================================================
# GEMINI MODEL
# ============================================================

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    max_retries=5,
)


# ============================================================
# ORCHESTRATOR
# ============================================================

def orchestrator(state: State) -> dict:

    planner = llm.with_structured_output(Plan)

    plan = planner.invoke(
        [
            SystemMessage(
                content=(

                    "You are an expert blog writer. Write ONE section "
                        "of the requested blog in Markdown.\n\n"

                    "Rules:\n"
                    "- Follow the original topic, section goal, and bullets.\n"
                    "- Stay relevant to the original topic.\n"
                    "- Explain concepts clearly for the intended audience.\n"
                    "- Do not introduce unrelated technologies or advanced "
                    "infrastructure details.\n"
                    "- Use simple examples and define technical terms.\n"
                    "- Include code only when relevant.\n"
                    "- Cover every provided bullet in order.\n"
                    "- Follow the target word count within ±15%.\n"
                    "- Start with a ## section heading.\n"
                    "- Return only the section content in Markdown.\n"
                    "- Do not include the main blog title."

                    
                )
            ),

            HumanMessage(
                content=f"Topic: {state['topic']}"
            ),
        ]
    )

    return {
        "plan": plan
    }


# ============================================================
# FANOUT
# ============================================================

def fanout(state: State):

    return [
        Send(
            "worker",
            {
                "task": task,
                "topic": state["topic"],
                "plan": state["plan"],
            },
        )
        for task in state["plan"].tasks
    ]


# ============================================================
# WORKER
# ============================================================

def worker(payload: dict) -> dict:

    task = payload["task"]
    topic = payload["topic"]
    plan = payload["plan"]

    bullets_text = "\n- " + "\n- ".join(task.bullets)

    # --------------------------------------------------------
    # Generate section
    # --------------------------------------------------------

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a senior technical writer and developer advocate. "
                    "Write ONE section of a technical blog post in Markdown.\n\n"

                    "Hard constraints:\n"

                    "- Follow the provided Goal and cover ALL Bullets "
                    "in order.\n"

                    "- Do not skip or merge bullets.\n"

                    "- Stay close to the Target words (±15%).\n"

                    "- Output ONLY the section content in Markdown.\n"

                    "- Do not include the blog title H1.\n"

                    "- Do not add extra commentary.\n\n"

                    "Technical quality bar:\n"

                    "- Be precise and implementation-oriented.\n"

                    "- Developers should be able to apply the information.\n"

                    "- Prefer concrete details over abstractions.\n"

                    "- Use APIs, data structures, protocols, and exact "
                    "technical terminology when relevant.\n"

                    "- When relevant, include at least one of:\n"
                    "  * a small code snippet\n"
                    "  * a tiny example input/output\n"
                    "  * a checklist of steps\n"
                    "  * a simple architecture/flow diagram in text\n"

                    "- Explain trade-offs briefly:\n"
                    "  performance, cost, complexity, reliability.\n"

                    "- Call out edge cases and failure modes.\n"

                    "- If you mention a best practice, explain why.\n\n"

                    "Markdown style:\n"

                    "- Start with a '## <Section Title>' heading.\n"
                    "- Use short paragraphs.\n"
                    "- Use bullet lists where helpful.\n"
                    "- Use code fences for code.\n"
                    "- Avoid fluff.\n"
                    "- Avoid marketing language.\n"
                    "- Keep code focused on the bullet being addressed.\n"
                )
            ),

            HumanMessage(
                content=(
                    f"Blog: {plan.blog_title}\n"
                    f"Audience: {plan.audience}\n"
                    f"Tone: {plan.tone}\n"
                    f"Topic: {topic}\n\n"
                    f"Section: {task.title}\n"
                    f"Section type: {task.section_type}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"Bullets:{bullets_text}\n"
                )
            ),
        ]
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Gemini content can be a string OR a list.
    # --------------------------------------------------------

    section_md = extract_text(response.content)

    # Safety check
    if not section_md:
        section_md = f"## {task.title}\n\nNo content was generated."

    return {
        "sections": [section_md]
    }


# ============================================================
# REDUCER
# ============================================================

def reducer(state: State) -> dict:

    title = state["plan"].blog_title

    body = "\n\n".join(state["sections"]).strip()

    final_md = f"# {title}\n\n{body}\n"

    # Create a safe filename
    filename = "".join(
        c if c.isalnum() or c in (" ", "_", "-") else ""
        for c in title
    )

    filename = filename.strip().lower().replace(" ", "_") + ".md"

    # Save the blog in the current working directory
    output_path = Path(filename).resolve()

    output_path.write_text(final_md, encoding="utf-8")

    # Print the exact file location in the terminal
    print(f"\nBlog saved successfully at:\n{output_path}")

    return {
        "final": final_md
    }


# ============================================================
# LANGGRAPH
# ============================================================

g = StateGraph(State)

g.add_node(
    "orchestrator",
    orchestrator
)

g.add_node(
    "worker",
    worker
)

g.add_node(
    "reducer",
    reducer
)


# ============================================================
# GRAPH EDGES
# ============================================================

g.add_edge(
    START,
    "orchestrator"
)

g.add_conditional_edges(
    "orchestrator",
    fanout,
    ["worker"]
)

g.add_edge(
    "worker",
    "reducer"
)

g.add_edge(
    "reducer",
    END
)


# ============================================================
# COMPILE GRAPH
# ============================================================

app = g.compile()




