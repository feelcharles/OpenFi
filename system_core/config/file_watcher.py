"""
File Watcher - 配置文件监控器

监控配置文件变化并触发重载

Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5
"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional
from threading import Thread, Event

logger = logging.getLogger(__name__)

class FileWatcher:
    """
    文件监控器
    
    监控指定文件的修改时间，当文件变化时触发回调函数
    
    Validates: Requirements 12.1, 12.2, 12.3
    """
    
    def __init__(self, file_path: str, callback: Callable[[], None], check_interval: float = 2.0):
        """
        初始化文件监控器
        
        Args:
            file_path: 要监控的文件路径
            callback: 文件变化时的回调函数
            check_interval: 检查间隔（秒）
            
        Validates: Requirement 12.1
        """
        self.file_path = Path(file_path)
        self.callback = callback
        self.check_interval = check_interval
        self.last_modified = self._get_modified_time()
        self.running = False
        self.thread: Optional[Thread] = None
        self.stop_event = Event()
        
        logger.info(f"FileWatcher initialized for: {self.file_path}")
    
    def _get_modified_time(self) -> float:
        """
        获取文件的最后修改时间
        
        Returns:
            修改时间戳，如果文件不存在返回0
        """
        try:
            if self.file_path.exists():
                return self.file_path.stat().st_mtime
        except Exception as e:
            logger.error(f"Failed to get file modified time: {e}")
        return 0.0
    
    def _watch_loop(self):
        """
        监控循环
        
        Validates: Requirements 12.1, 12.2
        """
        logger.info(f"FileWatcher started monitoring: {self.file_path}")
        
        while not self.stop_event.is_set():
            try:
                current_modified = self._get_modified_time()
                
                if current_modified > self.last_modified:
                    logger.info(f"File changed detected: {self.file_path}")
                    self.last_modified = current_modified
                    
                    try:
                        self.callback()
                        logger.info("Callback executed successfully")
                    except Exception as e:
                        logger.error(f"Callback execution failed: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error in watch loop: {e}", exc_info=True)
            
            # 等待下一次检查
            self.stop_event.wait(self.check_interval)
        
        logger.info("FileWatcher stopped")
    
    def start(self):
        """
        启动文件监控
        
        Validates: Requirement 12.1
        """
        if self.running:
            logger.warning("FileWatcher is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.thread = Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        
        logger.info("FileWatcher started")
    
    def stop(self):
        """
        停止文件监控
        
        Validates: Requirement 12.1
        """
        if not self.running:
            logger.warning("FileWatcher is not running")
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5.0)
        
        logger.info("FileWatcher stopped")
    
    def is_running(self) -> bool:
        """检查监控器是否正在运行"""
        return self.running
