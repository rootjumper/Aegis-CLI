"""LLM interaction logger for detailed tracing."""

import json
import inspect
from pathlib import Path
from datetime import datetime
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


class LLMLogger:
    """Logger for LLM prompts, responses, and interactions."""
    
    def __init__(self, log_dir: str = ".aegis/llm_logs", verbose: bool = False):
        """Initialize LLM logger.
        
        Args:
            log_dir: Directory for LLM interaction logs
            verbose: Whether to print to console in addition to file
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.console = Console()
        
        # Create session log file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_log = self.log_dir / f"session_{timestamp}.log"
        self.interaction_count = 0
    
    def _extract_tool_info(self, tools: Optional[list]) -> list[dict[str, Any]]:
        """Extract comprehensive tool information for logging.
        
        This method extracts detailed information from tool objects including:
        - Tool name
        - Description
        - Parameters/schema
        - Function signature
        - Type information
        
        Args:
            tools: List of tool objects (can be strings, callables, or tool instances)
            
        Returns:
            List of dictionaries containing tool information
        """
        tool_info = []
        
        for tool in (tools or []):
            if isinstance(tool, str):
                tool_info.append({"name": tool, "type": "string"})
                continue
            
            # Try to extract comprehensive tool information
            info: dict[str, Any] = {"type": str(type(tool).__name__)}
            
            # Name - try multiple attributes
            for attr in ['name', '__name__', 'function_name', 'tool_name']:
                if hasattr(tool, attr):
                    name_value = getattr(tool, attr)
                    if name_value:
                        info['name'] = name_value
                        break
            
            # Description - try multiple attributes
            for attr in ['description', '__doc__', 'tool_description']:
                if hasattr(tool, attr):
                    desc = getattr(tool, attr)
                    if desc:
                        # Clean up docstrings
                        if isinstance(desc, str):
                            desc = desc.strip()
                            # Take first line or first 200 chars
                            if '\n' in desc:
                                desc = desc.split('\n')[0]
                            if len(desc) > 200:
                                desc = desc[:200] + "..."
                        info['description'] = desc
                        break
            
            # Parameters/Schema - try multiple attributes
            for attr in ['parameters_schema', 'parameters', 'schema', 'input_schema', 'args_schema']:
                if hasattr(tool, attr):
                    params = getattr(tool, attr)
                    if params:
                        # Convert to dict if possible
                        if callable(params):
                            try:
                                params = params()
                            except Exception:
                                params = str(params)
                        
                        if hasattr(params, 'dict'):
                            try:
                                info['parameters'] = params.dict()
                            except Exception:
                                info['parameters'] = str(params)
                        elif hasattr(params, '__dict__'):
                            info['parameters'] = params.__dict__
                        elif isinstance(params, dict):
                            info['parameters'] = params
                        else:
                            info['parameters'] = str(params)
                        break
            
            # Callable signature
            if callable(tool):
                try:
                    sig = inspect.signature(tool)
                    info['signature'] = str(sig)
                except Exception:
                    pass
            
            # Try to get full representation (truncated)
            if hasattr(tool, '__dict__'):
                try:
                    full_dict = str(tool.__dict__)
                    if len(full_dict) > 300:
                        full_dict = full_dict[:300] + "..."
                    info['full_dict'] = full_dict
                except Exception:
                    pass
            
            tool_info.append(info)
        
        return tool_info
    
    def log_prompt(
        self,
        agent_name: str,
        prompt: str,
        model: str = "unknown",
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None
    ) -> int:
        """Log a prompt sent to LLM.
        
        Args:
            agent_name: Name of agent making the request
            prompt: The prompt text
            model: Model name
            system_prompt: System prompt if any
            tools: List of available tools
            
        Returns:
            Interaction ID for correlation with response
        """
        self.interaction_count += 1
        interaction_id = self.interaction_count
        
        # Extract comprehensive tool info
        tool_info = self._extract_tool_info(tools)
        
        log_entry = {
            "interaction_id": interaction_id,
            "timestamp": datetime.now().isoformat(),
            "type": "PROMPT",
            "agent": agent_name,
            "model": model,
            "prompt_length": len(prompt),
            "prompt": prompt,
            "system_prompt": system_prompt,
            "tools": tool_info  # Use comprehensive info instead of just names
        }
        
        # Write to session log
        with open(self.session_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{interaction_id}] PROMPT - {agent_name} → {model}\n")
            f.write(f"Time: {log_entry['timestamp']}\n")
            f.write(f"{'='*80}\n")
            if system_prompt:
                f.write(f"\nSYSTEM PROMPT:\n{system_prompt}\n\n")
            if tool_info:
                f.write(f"TOOLS ({len(tool_info)}):\n")
                for i, tool in enumerate(tool_info, 1):
                    f.write(f"\n  [{i}] {tool.get('name', 'unnamed')}\n")
                    if 'type' in tool:
                        f.write(f"      Type: {tool['type']}\n")
                    if 'description' in tool:
                        f.write(f"      Description: {tool['description']}\n")
                    if 'parameters' in tool:
                        # Pretty print parameters if it's a dict
                        params = tool['parameters']
                        if isinstance(params, dict):
                            params_str = json.dumps(params, indent=2)
                            # Indent each line
                            params_str = '\n'.join('      ' + line for line in params_str.split('\n'))
                            f.write(f"      Parameters:\n{params_str}\n")
                        else:
                            f.write(f"      Parameters: {params}\n")
                    if 'signature' in tool:
                        f.write(f"      Signature: {tool['signature']}\n")
                f.write("\n")
            else:
                f.write(f"TOOLS: None (text-based mode)\n\n")
            f.write(f"USER PROMPT ({len(prompt)} chars):\n{prompt}\n")
        
        # Console output if verbose
        if self.verbose:
            self.console.print(Panel(
                f"[bold cyan]Agent:[/bold cyan] {agent_name}\n"
                f"[bold cyan]Model:[/bold cyan] {model}\n"
                f"[bold cyan]Prompt Length:[/bold cyan] {len(prompt)} chars\n"
                f"[bold cyan]Tools:[/bold cyan] {len(tools or [])}",
                title=f"[{interaction_id}] 📤 PROMPT",
                border_style="cyan"
            ))
            
            # Show prompt with syntax highlighting
            self.console.print(Panel(
                prompt[:500] + ("..." if len(prompt) > 500 else ""),
                title="Prompt Preview",
                border_style="dim"
            ))
        
        return interaction_id
    
    def _extract_tool_calls_from_response(self, response: Any) -> list[dict[str, Any]]:
        """Extract detailed tool calls from PydanticAI response.
        
        This method extracts all tool calls made by the LLM including:
        - Tool names
        - Full parameters/arguments
        - Tool IDs if available
        
        Args:
            response: PydanticAI AgentRunResult
            
        Returns:
            List of dictionaries containing tool call information
        """
        tool_calls_data = []
        
        try:
            if not hasattr(response, 'all_messages'):
                return tool_calls_data
            
            messages = response.all_messages()
            if not messages:
                return tool_calls_data
            
            # Check each message for tool calls (not just last one)
            for msg_idx, msg in enumerate(messages):
                if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                    continue
                
                # Extract each tool call
                for tc_idx, tool_call in enumerate(msg.tool_calls):
                    tool_info = {
                        "message_index": msg_idx,
                        "call_index": tc_idx
                    }
                    
                    # Extract tool ID
                    if hasattr(tool_call, 'id'):
                        tool_info['id'] = tool_call.id
                    
                    # Extract tool name (try multiple attributes)
                    if hasattr(tool_call, 'function') and hasattr(tool_call.function, 'name'):
                        tool_info['name'] = tool_call.function.name
                    elif hasattr(tool_call, 'name'):
                        tool_info['name'] = tool_call.name
                    else:
                        tool_info['name'] = 'unknown'
                    
                    # Extract arguments/parameters (this is critical!)
                    args = None
                    if hasattr(tool_call, 'function') and hasattr(tool_call.function, 'arguments'):
                        args = tool_call.function.arguments
                    elif hasattr(tool_call, 'arguments'):
                        args = tool_call.arguments
                    
                    # Parse arguments if they're a JSON string
                    if isinstance(args, str):
                        try:
                            tool_info['parameters'] = json.loads(args)
                        except json.JSONDecodeError:
                            tool_info['parameters'] = args  # Keep as string if not valid JSON
                    elif isinstance(args, dict):
                        tool_info['parameters'] = args
                    else:
                        tool_info['parameters'] = str(args) if args else None
                    
                    # Extract type if available
                    if hasattr(tool_call, 'type'):
                        tool_info['type'] = tool_call.type
                    
                    tool_calls_data.append(tool_info)
        
        except Exception as e:
            # Log extraction error but don't fail
            tool_calls_data.append({
                "error": f"Failed to extract tool calls: {str(e)}",
                "type": "extraction_error"
            })
        
        return tool_calls_data
    
    def log_response(
        self,
        interaction_id: int,
        agent_name: str,
        response: Any,
        raw_response: Optional[str] = None,
        extracted_content: Optional[str] = None,
        tool_calls: Optional[list] = None,
        finish_reason: Optional[str] = None
    ):
        """Log a response from LLM.
        
        Args:
            interaction_id: ID from log_prompt call
            agent_name: Name of agent that made the request
            response: Response object (AgentRunResult or similar)
            raw_response: Raw response text if available
            extracted_content: Content extracted by parser
            tool_calls: Tool calls made by LLM (if None, will auto-extract from response)
            finish_reason: Why the response ended
        """
        # Try to extract raw content from response object
        if raw_response is None and hasattr(response, 'all_messages'):
            try:
                messages = response.all_messages()
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, 'parts') and last_msg.parts:
                        raw_response = getattr(last_msg.parts[0], 'content', str(last_msg.parts[0]))
                    elif hasattr(last_msg, 'content'):
                        raw_response = last_msg.content
            except Exception:
                raw_response = str(response)
        
        # Auto-extract tool calls if not provided (CRITICAL FIX)
        if tool_calls is None:
            tool_calls = self._extract_tool_calls_from_response(response)
        
        log_entry = {
            "interaction_id": interaction_id,
            "timestamp": datetime.now().isoformat(),
            "type": "RESPONSE",
            "agent": agent_name,
            "raw_response": raw_response or "",
            "extracted_content": extracted_content,
            "tool_calls": tool_calls or [],
            "finish_reason": finish_reason,
            "response_length": len(raw_response or "")
        }
        
        # Write to session log with DETAILED tool call information
        with open(self.session_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'-'*80}\n")
            f.write(f"[{interaction_id}] RESPONSE - {agent_name}\n")
            f.write(f"Time: {log_entry['timestamp']}\n")
            f.write(f"Finish Reason: {finish_reason or 'unknown'}\n")
            f.write(f"{'-'*80}\n")
            
            # ENHANCED: Show detailed tool calls with full parameters
            if tool_calls:
                f.write(f"\nTOOL CALLS ({len(tool_calls)}):\n")
                for idx, tc in enumerate(tool_calls, 1):
                    f.write(f"\n  [{idx}] Tool Call:\n")
                    
                    # Handle both dict format (new) and simple format (legacy)
                    if isinstance(tc, dict):
                        if 'name' in tc:
                            f.write(f"      Name: {tc['name']}\n")
                        if 'id' in tc:
                            f.write(f"      ID: {tc['id']}\n")
                        if 'type' in tc:
                            f.write(f"      Type: {tc['type']}\n")
                        if 'parameters' in tc and tc['parameters']:
                            f.write(f"      Parameters:\n")
                            # Pretty print parameters
                            params_str = json.dumps(tc['parameters'], indent=4)
                            # Indent each line for readability
                            for line in params_str.split('\n'):
                                f.write(f"        {line}\n")
                        if 'error' in tc:
                            f.write(f"      ERROR: {tc['error']}\n")
                    else:
                        # Legacy format or simple string
                        f.write(f"      {tc}\n")
                f.write("\n")
            else:
                f.write(f"\nTOOL CALLS: None (text-based response)\n\n")
            
            if raw_response:
                f.write(f"\nRAW RESPONSE ({len(raw_response)} chars):\n{raw_response}\n")
            
            if extracted_content:
                f.write(f"\nEXTRACTED CONTENT ({len(extracted_content)} chars):\n{extracted_content}\n")
        
        # Console output if verbose
        if self.verbose:
            self.console.print(Panel(
                f"[bold green]Agent:[/bold green] {agent_name}\n"
                f"[bold green]Response Length:[/bold green] {len(raw_response or '')} chars\n"
                f"[bold green]Extracted:[/bold green] {len(extracted_content or '')} chars\n"
                f"[bold green]Tool Calls:[/bold green] {len(tool_calls or [])}",
                title=f"[{interaction_id}] 📥 RESPONSE",
                border_style="green"
            ))
            
            # Show detailed tool calls if present
            if tool_calls:
                for idx, tc in enumerate(tool_calls, 1):
                    if isinstance(tc, dict) and 'name' in tc:
                        params_preview = ""
                        if 'parameters' in tc and tc['parameters']:
                            params_str = json.dumps(tc['parameters'], indent=2)
                            if len(params_str) > 200:
                                params_str = params_str[:200] + "..."
                            params_preview = f"\n[dim]Parameters:[/dim]\n{params_str}"
                        
                        self.console.print(Panel(
                            f"[bold cyan]Name:[/bold cyan] {tc.get('name', 'unknown')}\n"
                            f"[bold cyan]ID:[/bold cyan] {tc.get('id', 'N/A')}"
                            + params_preview,
                            title=f"🔧 Tool Call [{idx}/{len(tool_calls)}]",
                            border_style="cyan"
                        ))
            
            if extracted_content:
                # Show extracted content with syntax highlighting
                self.console.print(Panel(
                    Syntax(
                        extracted_content[:500] + ("..." if len(extracted_content) > 500 else ""),
                        "python",
                        theme="monokai",
                        line_numbers=False
                    ),
                    title="Extracted Content Preview",
                    border_style="dim"
                ))
    
    def log_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        parameters: dict,
        result: Any,
        success: bool,
        error: Optional[str] = None
    ):
        """Log a tool call and its result.
        
        Args:
            agent_name: Name of agent making the call
            tool_name: Name of tool being called
            parameters: Tool parameters
            result: Tool result
            success: Whether call succeeded
            error: Error message if failed
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "TOOL_CALL",
            "agent": agent_name,
            "tool": tool_name,
            "parameters": parameters,
            "success": success,
            "error": error,
            "result_preview": str(result)[:200] if result else None
        }
        
        # Write to session log with FULL details
        with open(self.session_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'~'*80}\n")
            f.write(f"TOOL CALL - {agent_name} → {tool_name}\n")
            f.write(f"Time: {log_entry['timestamp']}\n")
            f.write(f"Success: {success}\n")
            f.write(f"{'~'*80}\n")
            
            # ENHANCED: Show full parameters with pretty printing
            f.write(f"\nParameters:\n")
            if parameters:
                params_str = json.dumps(parameters, indent=4)
                for line in params_str.split('\n'):
                    f.write(f"  {line}\n")
            else:
                f.write("  (none)\n")
            
            if error:
                f.write(f"\nError: {error}\n")
            
            if result:
                result_str = str(result)
                # Show more of the result (increased from 500 to 1000 chars)
                max_result_len = 1000
                if len(result_str) > max_result_len:
                    f.write(f"\nResult ({len(result_str)} chars, showing first {max_result_len}):\n")
                    f.write(f"{result_str[:max_result_len]}\n... (truncated)\n")
                else:
                    f.write(f"\nResult ({len(result_str)} chars):\n{result_str}\n")
        
        # Console output if verbose
        if self.verbose:
            status_color = "green" if success else "red"
            status_icon = "✓" if success else "✗"
            
            # Format parameters for display
            params_display = ""
            if parameters:
                params_str = json.dumps(parameters, indent=2)
                if len(params_str) > 300:
                    params_str = params_str[:300] + "..."
                params_display = f"\n[dim]Parameters:[/dim]\n{params_str}"
            
            self.console.print(Panel(
                f"[bold {status_color}]Tool:[/bold {status_color}] {tool_name}\n"
                f"[bold {status_color}]Agent:[/bold {status_color}] {agent_name}\n"
                f"[bold {status_color}]Status:[/bold {status_color}] {status_icon}"
                + params_display
                + (f"\n[bold red]Error:[/bold red] {error}" if error else ""),
                title=f"🔧 TOOL CALL",
                border_style=status_color
            ))
    
    def log_file_operation(
        self,
        agent_name: str,
        operation: str,
        file_path: str,
        success: bool,
        content_preview: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log a file operation.
        
        Args:
            agent_name: Name of agent performing operation
            operation: Type of operation (write, read, delete, etc.)
            file_path: Path to file
            success: Whether operation succeeded
            content_preview: Preview of file content
            error: Error message if failed
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "FILE_OP",
            "agent": agent_name,
            "operation": operation,
            "path": file_path,
            "success": success,
            "error": error
        }
        
        # Write to session log
        with open(self.session_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'*'*80}\n")
            f.write(f"FILE OPERATION - {agent_name}\n")
            f.write(f"Time: {log_entry['timestamp']}\n")
            f.write(f"Operation: {operation}\n")
            f.write(f"Path: {file_path}\n")
            f.write(f"Success: {success}\n")
            f.write(f"{'*'*80}\n")
            if error:
                f.write(f"Error: {error}\n")
            if content_preview:
                f.write(f"Content Preview:\n{content_preview[:300]}\n")
        
        # Console output if verbose
        if self.verbose:
            status_color = "green" if success else "red"
            status_icon = "✓" if success else "✗"
            
            self.console.print(Panel(
                f"[bold {status_color}]Operation:[/bold {status_color}] {operation}\n"
                f"[bold {status_color}]Path:[/bold {status_color}] {file_path}\n"
                f"[bold {status_color}]Status:[/bold {status_color}] {status_icon}\n"
                + (f"[bold red]Error:[/bold red] {error}" if error else ""),
                title=f"📁 FILE OPERATION",
                border_style=status_color
            ))
    
    def get_session_summary(self) -> dict:
        """Get summary of current session.
        
        Returns:
            Summary dictionary
        """
        return {
            "session_log": str(self.session_log),
            "interactions": self.interaction_count,
            "log_size": self.session_log.stat().st_size if self.session_log.exists() else 0
        }
