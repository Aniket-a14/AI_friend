# 🤝 Contributing to AI Friend

Thank you for your interest in contributing to AI Friend! This document provides guidelines and best practices for contributing to the project.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing](#testing)
6. [Pull Request Process](#pull-request-process)
7. [Issue Guidelines](#issue-guidelines)

---

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please read [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) before contributing.

---

## Getting Started

### Prerequisites

- **Python 3.10+** for backend development
- **Node.js 22+** for frontend development
- **Docker & Docker Compose** for full-stack development
- **Git** for version control

### Fork and Clone

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/AI_friend.git
cd AI_friend

# 3. Add upstream remote
git remote add upstream https://github.com/Aniket-a14/AI_friend.git

# 4. Create a feature branch
git checkout -b feature/your-feature-name
```

### Local Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run development server
python main.py
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with backend URL

# Run development server
npm run dev
```

#### v3.0 Infrastructure (Optional)

```bash
# Start NATS and Neo4j
docker compose -f docker-compose.infra.yml up -d

# Verify
docker ps
```

---

## Development Workflow

### 1. Sync with Upstream

Before starting work, sync your fork with the upstream repository:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

### 2. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

**Branch Naming Conventions**:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/updates
- `chore/` - Maintenance tasks

### 3. Make Changes

- Write clean, readable code
- Follow coding standards (see below)
- Add tests for new features
- Update documentation as needed

### 4. Commit Changes

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git add .
git commit -m "feat: add voice cloning support"
```

**Commit Types**:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `style:` - Code style (formatting, no logic change)
- `refactor:` - Code restructuring
- `test:` - Adding tests
- `chore:` - Maintenance

**Examples**:
```bash
git commit -m "feat: add Neo4j GraphRAG integration"
git commit -m "fix: resolve WebSocket connection timeout"
git commit -m "docs: update API_SPEC.md with new endpoints"
git commit -m "refactor: extract memory logic into separate module"
```

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Coding Standards

### Python (Backend)

#### Style Guide

Follow [PEP 8](https://pep8.org/) with these specifics:

- **Line Length**: 100 characters max
- **Indentation**: 4 spaces
- **Imports**: Grouped and sorted (stdlib, third-party, local)
- **Type Hints**: Required for all function signatures

**Example**:
```python
from typing import Optional, List
import asyncio

from fastapi import WebSocket
from app.models import Message


async def process_audio(
    audio_data: bytes,
    session_id: str,
    user_id: Optional[str] = None
) -> List[Message]:
    """
    Process audio data and return conversation messages.
    
    Args:
        audio_data: Raw PCM audio bytes
        session_id: Unique session identifier
        user_id: Optional user identifier
        
    Returns:
        List of conversation messages
    """
    # Implementation
    pass
```

#### Linting

```bash
# Install linting tools
pip install flake8 black mypy

# Run linters
flake8 app/
black app/ --check
mypy app/
```

**Configuration** (`.flake8`):
```ini
[flake8]
max-line-length = 100
exclude = .venv,__pycache__
ignore = E203,W503
```

### TypeScript/JavaScript (Frontend)

#### Style Guide

- **Line Length**: 100 characters max
- **Indentation**: 2 spaces
- **Quotes**: Single quotes for strings
- **Semicolons**: Required
- **Type Safety**: Strict TypeScript

**Example**:
```typescript
interface AudioConfig {
  sampleRate: number;
  channels: number;
  bitDepth: number;
}

async function captureAudio(config: AudioConfig): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: config.sampleRate,
      channelCount: config.channels,
    },
  });
  
  return stream;
}
```

#### Linting

```bash
# Run ESLint
npm run lint

# Fix auto-fixable issues
npm run lint:fix

# Type check
npm run type-check
```

### React Best Practices

- Use functional components with hooks
- Prefer `const` over `let`
- Use TypeScript interfaces for props
- Extract reusable logic into custom hooks
- Keep components small and focused

**Example**:
```typescript
interface VoiceInterfaceProps {
  onAudioData: (data: ArrayBuffer) => void;
  isActive: boolean;
}

export const VoiceInterface: React.FC<VoiceInterfaceProps> = ({
  onAudioData,
  isActive,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  
  useEffect(() => {
    if (isActive) {
      startRecording();
    } else {
      stopRecording();
    }
  }, [isActive]);
  
  return (
    <div className="voice-interface">
      {/* Component JSX */}
    </div>
  );
};
```

---

## Testing

### Backend Tests

```bash
cd backend

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

**Test Structure**:
```python
import pytest
from app.memory_store import MemoryStore


@pytest.mark.asyncio
async def test_memory_storage():
    """Test memory entry storage and retrieval."""
    store = MemoryStore()
    
    # Store memory
    entry_id = await store.store(
        content="User likes blue",
        type="preference"
    )
    
    # Retrieve memory
    results = await store.query("favorite color")
    
    assert len(results) > 0
    assert results[0].content == "User likes blue"
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
npm test

# Run with coverage
npm test -- --coverage

# Run E2E tests
npm run test:e2e
```

**Test Structure** (Jest + React Testing Library):
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { VoiceInterface } from './VoiceInterface';

describe('VoiceInterface', () => {
  it('should start recording when activated', () => {
    const onAudioData = jest.fn();
    
    render(
      <VoiceInterface onAudioData={onAudioData} isActive={true} />
    );
    
    const button = screen.getByRole('button', { name: /start/i });
    fireEvent.click(button);
    
    expect(onAudioData).toHaveBeenCalled();
  });
});
```

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream**: Ensure your branch is up-to-date
2. **Run tests**: All tests must pass
3. **Run linters**: Code must pass linting checks
4. **Update docs**: Update README, API_SPEC, etc. if needed
5. **Test locally**: Verify changes work end-to-end

### PR Template

When creating a PR, use this template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Tested locally

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
```

### Review Process

1. **Automated Checks**: CI/CD must pass
2. **Code Review**: At least one maintainer approval required
3. **Testing**: Reviewer may request additional tests
4. **Documentation**: Ensure all changes are documented

### After Approval

Maintainers will merge your PR. Your contribution will be included in the next release!

---

## Issue Guidelines

### Reporting Bugs

Use the bug report template:

```markdown
**Describe the bug**
Clear description of the issue

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What should happen

**Screenshots**
If applicable

**Environment**
- OS: [e.g., Windows 11]
- Browser: [e.g., Chrome 120]
- Version: [e.g., 2.2.0]

**Additional context**
Any other relevant information
```

### Feature Requests

Use the feature request template:

```markdown
**Is your feature request related to a problem?**
Clear description of the problem

**Describe the solution you'd like**
What you want to happen

**Describe alternatives you've considered**
Other solutions you've thought about

**Additional context**
Any other relevant information
```

---

## Codebase Structure

### Backend (`/backend`)

```
backend/
├── app/
│   ├── agents/           # v3.0 micro-agents
│   │   └── base.py       # BaseAgent abstraction
│   ├── knowledge/        # GraphRAG components
│   │   ├── graph_db.py   # Neo4j connector
│   │   └── triple_extractor.py
│   ├── gemini_live.py    # Gemini Live client
│   ├── llm.py            # LLM orchestration
│   └── memory_store.py   # RAG memory
├── tools/                # Client tools
├── tests/                # Test suite
├── main.py               # FastAPI app
└── requirements.txt      # Dependencies
```

### Frontend (`/frontend`)

```
frontend/
├── app/                  # Next.js App Router
│   ├── page.tsx          # Landing page
│   └── layout.tsx        # Root layout
├── components/           # React components
│   ├── VoiceInterface.tsx
│   └── AudioWorklet.ts
├── public/               # Static assets
└── package.json          # Dependencies
```

---

## Getting Help

- **Questions**: Open a [Discussion](https://github.com/Aniket-a14/AI_friend/discussions)
- **Bugs**: Open an [Issue](https://github.com/Aniket-a14/AI_friend/issues)
- **Security**: See [SECURITY.md](./SECURITY.md)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to AI Friend!** 🎉
