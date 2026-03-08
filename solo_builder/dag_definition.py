"""Initial DAG definition for Solo Builder."""
from typing import Any, Dict

INITIAL_DAG: Dict[str, Any] = {
    "Task 0": {
        "status": "Running",
        "depends_on": [],
        "branches": {
            "Branch A": {
                "status": "Running",
                "subtasks": {
                    "A1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 5 key features a solo developer AI project management tool needs. Bullet points.", "output": ""},
                    "A2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a 2-sentence elevator pitch for Solo Builder — a Python terminal CLI that uses AI agents to track DAG-based project tasks.", "output": ""},
                    "A3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Suggest 3 concrete improvements to make Solo Builder more useful for a solo developer.", "output": ""},
                    "A4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 risks of building a self-healing agent system, and one mitigation for each?", "output": ""},
                    "A5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a tagline for Solo Builder in under 10 words.", "output": ""},
                },
            },
            "Branch B": {
                "status": "Pending",
                "subtasks": {
                    "B1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the difference between a Shadow Agent and a Verifier agent in 2 sentences.", "output": ""},
                    "B2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 real-world use cases for a DAG-based AI project tracker.", "output": ""},
                    "B3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "In one sentence, explain what a MetaOptimizer does in an AI pipeline.", "output": ""},
                },
            },
        },
    },
    "Task 1": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch C": {
                "status": "Pending",
                "subtasks": {
                    "C1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What does a DAG (Directed Acyclic Graph) represent in software project management? Answer in one paragraph.", "output": ""},
                    "C2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 advantages of using a priority queue to schedule software tasks.", "output": ""},
                    "C3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Explain the concept of task staleness in a project management system in 2 sentences.", "output": ""},
                    "C4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a shadow state in an agent-based system? Give one concrete example.", "output": ""},
                },
            },
            "Branch D": {
                "status": "Pending",
                "subtasks": {
                    "D1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe 2 strategies for preventing task starvation in a priority-based scheduler.", "output": ""},
                    "D2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between optimistic and pessimistic task verification? One paragraph.", "output": ""},
                },
            },
        },
    },
    "Task 2": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch E": {
                "status": "Pending",
                "subtasks": {
                    "E1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 benefits of self-healing automation in a software pipeline?", "output": ""},
                    "E2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe how a MetaOptimizer could improve agent performance over time. 2 sentences.", "output": ""},
                    "E3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 metrics that indicate an AI agent system is performing well.", "output": ""},
                    "E4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between reactive and proactive error handling in agent systems? One sentence each.", "output": ""},
                    "E5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Give one example of a heuristic weight that a MetaOptimizer might adjust in a task planner.", "output": ""},
                },
            },
            "Branch F": {
                "status": "Pending",
                "subtasks": {
                    "F1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the role of a Verifier agent in a multi-agent pipeline? 2 sentences.", "output": ""},
                    "F2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe how memory snapshots help with debugging in an agent system. One paragraph.", "output": ""},
                    "F3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 2 ways a ShadowAgent could detect state inconsistencies in a DAG pipeline.", "output": ""},
                    "F4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between a branch and a task in a DAG-based project tracker? One sentence.", "output": ""},
                },
            },
        },
    },
    "Task 3": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch G": {
                "status": "Pending",
                "subtasks": {
                    "G1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is continuous integration and how does it relate to automated project management? One paragraph.", "output": ""},
                    "G2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 common causes of technical debt in solo developer projects.", "output": ""},
                    "G3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the MVP (Minimum Viable Product) concept in 2 sentences.", "output": ""},
                    "G4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a sprint in agile methodology? One sentence.", "output": ""},
                    "G5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 developer tools a solo builder could use alongside an AI task manager.", "output": ""},
                    "G6": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the difference between async and sync task execution in pipelines? One paragraph.", "output": ""},
                },
            },
            "Branch H": {
                "status": "Pending",
                "subtasks": {
                    "H1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of a 'Definition of Done' in software projects. 2 sentences.", "output": ""},
                    "H2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 ways to reduce context-switching costs for a solo developer.", "output": ""},
                    "H3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is the Pomodoro technique and how might it help a solo developer? One paragraph.", "output": ""},
                    "H4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Give 2 examples of how AI can assist with project estimation for a solo developer.", "output": ""},
                },
            },
            "Branch I": {
                "status": "Pending",
                "subtasks": {
                    "I1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is scope creep and how can a solo developer prevent it? One paragraph.", "output": ""},
                    "I2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 warning signs that a solo software project is at risk of failure.", "output": ""},
                    "I3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of 'bikeshedding' and why it's a risk for solo developers. 2 sentences.", "output": ""},
                },
            },
        },
    },
    "Task 4": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch J": {
                "status": "Pending",
                "subtasks": {
                    "J1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 principles of clean code that every solo developer should follow?", "output": ""},
                    "J2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the DRY (Don't Repeat Yourself) principle in one sentence with a concrete example.", "output": ""},
                    "J3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a code smell? Give 3 examples.", "output": ""},
                    "J4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Pick 3 of the SOLID principles and explain each in one bullet point.", "output": ""},
                    "J5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is test-driven development (TDD)? Describe it in 2 sentences.", "output": ""},
                    "J6": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 benefits of writing unit tests for a solo developer project.", "output": ""},
                    "J7": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a linter and why should solo developers use one? One paragraph.", "output": ""},
                    "J8": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the difference between unit tests and integration tests in one sentence each.", "output": ""},
                },
            },
            "Branch K": {
                "status": "Pending",
                "subtasks": {
                    "K1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is semantic versioning (semver)? Give one example of a version bump and why.", "output": ""},
                    "K2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 best practices for writing clear git commit messages.", "output": ""},
                    "K3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a pull request and how does it help with code quality? One paragraph.", "output": ""},
                    "K4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of self-code-review for a solo developer. 2 sentences.", "output": ""},
                    "K5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is continuous deployment and how does it benefit a solo developer project? 2 sentences.", "output": ""},
                },
            },
        },
    },
    "Task 5": {
        "status": "Pending",
        "depends_on": ["Task 0"],
        "branches": {
            "Branch L": {
                "status": "Pending",
                "subtasks": {
                    "L1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 key metrics a solo developer should track for a CLI tool project?", "output": ""},
                    "L2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of a project roadmap in 2 sentences.", "output": ""},
                    "L3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 ways to gather user feedback on a solo developer CLI tool.", "output": ""},
                    "L4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is feature prioritization and why is it important for solo developers? One paragraph.", "output": ""},
                    "L5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe 2 ways AI can help a solo developer with project documentation.", "output": ""},
                    "L6": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a changelog and why should every project have one? One sentence.", "output": ""},
                },
            },
            "Branch M": {
                "status": "Pending",
                "subtasks": {
                    "M1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 strategies for getting early users for a solo developer tool.", "output": ""},
                    "M2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is developer experience (DX) and why does it matter? One paragraph.", "output": ""},
                    "M3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe 2 ways to measure whether a solo developer project is succeeding.", "output": ""},
                    "M4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is open source and what are 2 benefits of open-sourcing a solo developer project?", "output": ""},
                },
            },
            "Branch N": {
                "status": "Pending",
                "subtasks": {
                    "N1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What are 3 signs that a software project is ready for its first public release?", "output": ""},
                    "N2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe the concept of a 'soft launch' for a developer tool. 2 sentences.", "output": ""},
                    "N3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "List 3 things a developer should document before releasing an open-source project.", "output": ""},
                    "N4": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What is a README file and what are its 3 most important sections? One sentence each.", "output": ""},
                    "N5": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a one-sentence mission statement for Solo Builder — an AI-powered CLI that manages DAG-based tasks for solo developers.", "output": ""},
                },
            },
        },
    },
    "Task 6": {
        "status": "Pending",
        "depends_on": ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"],
        "branches": {
            "Branch O": {
                "status": "Pending",
                "subtasks": {
                    "O1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Read the file state/solo_builder_state.json. Summarize in 3 bullet points: how many tasks completed, which task had the most subtasks, and one notable Claude output found in the data.", "output": "", "tools": "Read,Glob,Grep"},
                    "O2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Describe how self-healing agents reduce manual intervention in a software project pipeline. One paragraph.", "output": ""},
                    "O3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a 3-sentence executive summary of Solo Builder for a developer audience.", "output": ""},
                },
            },
            "Branch P": {
                "status": "Pending",
                "subtasks": {
                    "P1": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "What would a 'v2.0' of Solo Builder look like? List 3 major new features with one sentence each.", "output": ""},
                    "P2": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "How would you adapt Solo Builder for a team of 3-5 developers instead of a solo developer? Give 3 key changes.", "output": ""},
                    "P3": {"status": "Pending", "shadow": "Pending", "last_update": 0, "description": "Write a haiku about software agents managing project tasks autonomously.", "output": ""},
                },
            },
        },
    },
}
