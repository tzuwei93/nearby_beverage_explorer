"""Command execution module"""

import logging
import subprocess
import select # ADDED

logger = logging.getLogger(__name__)

class CommandRunner:
    """Handles command execution and logging"""
    
    def run(self, command, check_success=True):
        """Run a shell command and stream output live.
        
        Args:
            command (str): Command to execute
            check_success (bool): If True, raise exception on non-zero exit code
                                If False, return False on non-zero exit code
        
        Returns:
            bool: True if command succeeded, False otherwise
            
        Raises:
            Exception: If command fails and check_success is True
        """
        logger.info(f"Running command: {command}")
        
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line-buffered
                universal_newlines=True # Ensure text mode for stdout/stderr
            )
            
            stderr_output_list = []

            # Prepare for select - works on macOS/Linux for pipes
            fds_to_pipes = {}
            if process.stdout:
                fds_to_pipes[process.stdout.fileno()] = process.stdout
            if process.stderr:
                fds_to_pipes[process.stderr.fileno()] = process.stderr
            
            active_filenos = list(fds_to_pipes.keys())

            while active_filenos:
                readable_fds, _, _ = select.select(active_filenos, [], [], 0.1) # 0.1s timeout for responsiveness

                for fd in readable_fds:
                    pipe = fds_to_pipes[fd]
                    line = pipe.readline() # Reads until newline or EOF
                    if line: # If line is not empty string (which means EOF for that read)
                        line = line.strip()
                        if line: # If line has content after stripping
                            if pipe is process.stdout:
                                logger.info(line)
                                print(line) # Live print stdout
                            elif pipe is process.stderr:
                                logger.warning(line)
                                print(line) # Live print stderr
                                stderr_output_list.append(line)
                    else: # pipe.readline() returned empty string, meaning EOF for this pipe
                        active_filenos.remove(fd)
                        # pipe.close() is not strictly necessary here, Popen manages pipe lifecycle.
            
            # All pipes have reached EOF and been removed from active_filenos.
            # Now, wait for the process to terminate to get the return code.
            process.wait() 
            return_code = process.returncode
            
            stderr_output_str = "\\n".join(stderr_output_list)

            if return_code != 0:
                error_message = f"Command failed with exit code {return_code}"
                if stderr_output_str: # Check if there's any stderr content
                    error_message += f"\\nStderr:\\n{stderr_output_str.strip()}" # Add stripped stderr
                
                logger.error(error_message)
                if check_success:
                    raise Exception(error_message)
                return False
            
            return True
            
        except Exception as e: # Catch other potential exceptions like command not found
            logger.error(f"Command execution failed: {str(e)}")
            if check_success:
                raise
            return False