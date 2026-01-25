"""State management for Aegis-CLI using SQLite.

This module provides persistent storage for tasks, tool calls, reasoning traces,
and agent memory using SQLite with async support.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker

Base = declarative_base()


class Task(Base):
    """SQLAlchemy model for tasks."""
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class ToolCallRecord(Base):
    """SQLAlchemy model for tool calls."""
    __tablename__ = "tool_calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    params_json = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class ReasoningTrace(Base):
    """SQLAlchemy model for reasoning traces."""
    __tablename__ = "reasoning_traces"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class AgentMemory(Base):
    """SQLAlchemy model for agent memory."""
    __tablename__ = "agent_memory"
    
    key = Column(String, primary_key=True)
    value_json = Column(Text, nullable=False)
    agent_name = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StateManager:
    """Manages persistent state for Aegis-CLI.
    
    Provides methods to store and retrieve tasks, tool calls, reasoning traces,
    and agent memory using SQLite with async support.
    """
    
    def __init__(self, db_path: str = ".aegis/session.db") -> None:
        """Initialize the state manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_directory()
        self.engine: AsyncEngine | None = None
        self.session_maker: async_sessionmaker[AsyncSession] | None = None
    
    def _ensure_directory(self) -> None:
        """Ensure the .aegis directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    async def init_database(self) -> None:
        """Create database tables if they don't exist."""
        # Create async engine
        db_url = f"sqlite+aiosqlite:///{self.db_path}"
        self.engine = create_async_engine(db_url, echo=False)
        self.session_maker = async_sessionmaker(
            self.engine, expire_on_commit=False
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
    
    async def store_task(
        self,
        task_id: str,
        task_type: str,
        payload: dict[str, Any],
        status: str = "PENDING"
    ) -> None:
        """Store a task in the database.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task
            payload: Task payload
            status: Task status
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            task = Task(
                id=task_id,
                type=task_type,
                payload_json=json.dumps(payload),
                status=status
            )
            session.add(task)
            await session.commit()
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        completed: bool = False
    ) -> None:
        """Update the status of a task.
        
        Args:
            task_id: Task identifier
            status: New status
            completed: Whether the task is completed
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            from sqlalchemy import select, update
            stmt = (
                update(Task)
                .where(Task.id == task_id)
                .values(
                    status=status,
                    completed_at=datetime.utcnow() if completed else None
                )
            )
            await session.execute(stmt)
            await session.commit()
    
    async def get_task_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent task history.
        
        Args:
            limit: Maximum number of tasks to retrieve
            
        Returns:
            List of task dictionaries
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            from sqlalchemy import select
            stmt = (
                select(Task)
                .order_by(Task.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            return [
                {
                    "id": task.id,
                    "type": task.type,
                    "payload": json.loads(task.payload_json),
                    "status": task.status,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                }
                for task in tasks
            ]
    
    async def store_tool_call(
        self,
        task_id: str,
        tool_name: str,
        params: dict[str, Any],
        result: Any = None
    ) -> None:
        """Store a tool call record.
        
        Args:
            task_id: Associated task ID
            tool_name: Name of the tool
            params: Tool parameters
            result: Tool result
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            tool_call = ToolCallRecord(
                task_id=task_id,
                tool_name=tool_name,
                params_json=json.dumps(params),
                result_json=json.dumps(result) if result is not None else None
            )
            session.add(tool_call)
            await session.commit()
    
    async def store_reasoning(
        self,
        task_id: str,
        agent_name: str,
        content: str
    ) -> None:
        """Store reasoning trace.
        
        Args:
            task_id: Associated task ID
            agent_name: Name of the agent
            content: Reasoning content
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            trace = ReasoningTrace(
                task_id=task_id,
                agent_name=agent_name,
                content=content
            )
            session.add(trace)
            await session.commit()
    
    async def remember(
        self,
        key: str,
        value: Any,
        agent_name: str,
        ttl: int = 3600
    ) -> None:
        """Store a value in agent memory.
        
        Args:
            key: Memory key
            value: Value to store
            agent_name: Agent name
            ttl: Time to live in seconds
        """
        if not self.session_maker:
            await self.init_database()
        
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        async with self.session_maker() as session:  # type: ignore
            from sqlalchemy import select
            stmt = select(AgentMemory).where(AgentMemory.key == key)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.value_json = json.dumps(value)
                existing.expires_at = expires_at
            else:
                memory = AgentMemory(
                    key=key,
                    value_json=json.dumps(value),
                    agent_name=agent_name,
                    expires_at=expires_at
                )
                session.add(memory)
            
            await session.commit()
    
    async def recall(
        self,
        key: str,
        agent_name: str | None = None
    ) -> Any:
        """Recall a value from agent memory.
        
        Args:
            key: Memory key
            agent_name: Optional agent name filter
            
        Returns:
            Stored value or None
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            from sqlalchemy import select, and_
            stmt = select(AgentMemory).where(AgentMemory.key == key)
            
            if agent_name:
                stmt = stmt.where(AgentMemory.agent_name == agent_name)
            
            result = await session.execute(stmt)
            memory = result.scalar_one_or_none()
            
            if not memory:
                return None
            
            # Check if expired
            if memory.expires_at and memory.expires_at < datetime.utcnow():
                await session.delete(memory)
                await session.commit()
                return None
            
            return json.loads(memory.value_json)
    
    async def forget(self, key: str) -> None:
        """Delete a value from agent memory.
        
        Args:
            key: Memory key
        """
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            from sqlalchemy import delete
            stmt = delete(AgentMemory).where(AgentMemory.key == key)
            await session.execute(stmt)
            await session.commit()
    
    async def clear_expired_memory(self) -> None:
        """Remove expired memory entries."""
        if not self.session_maker:
            await self.init_database()
        
        async with self.session_maker() as session:  # type: ignore
            from sqlalchemy import delete, and_
            stmt = delete(AgentMemory).where(
                and_(
                    AgentMemory.expires_at.isnot(None),
                    AgentMemory.expires_at < datetime.utcnow()
                )
            )
            await session.execute(stmt)
            await session.commit()


# Global state manager instance
_state_manager: StateManager | None = None


def get_state_manager(db_path: str = ".aegis/session.db") -> StateManager:
    """Get or create the global state manager instance.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        StateManager instance
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(db_path)
    return _state_manager
