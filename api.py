#!/usr/bin/env python3
"""
REST API Server for RTLS Tag Management System
Provides endpoints for tag registration and status monitoring
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import threading
import time
import logging
from datetime import datetime
import asyncio
import uvicorn

# Import our tag processor
from main import TagProcessor

# Pydantic models for API
class TagRegistration(BaseModel):
    """Model for tag registration"""
    id: str = Field(..., description="Tag ID (hexadecimal string)")
    description: str = Field(..., description="Human readable description of the tag")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "fa451f0755d8",
                "description": "Helmet Tag for worker A"
            }
        }

class TagStatus(BaseModel):
    """Model for tag status response"""
    id: str
    description: str
    last_cnt: Optional[int] = None
    last_seen: Optional[str] = None
    is_registered: bool = True
    total_updates: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "fa451f0755d8",
                "description": "Helmet Tag for worker A",
                "last_cnt": 198,
                "last_seen": "2024-05-03T14:00:59.456",
                "is_registered": True,
                "total_updates": 42
            }
        }

class HealthStatus(BaseModel):
    """Model for health check response"""
    status: str
    timestamp: str
    uptime: Optional[str] = None
    active_tags: int = 0
    total_processed: int = 0
    total_errors: int = 0

class TagRegistry:
    """Registry for managing registered tags"""
    
    def __init__(self):
        self.registered_tags: Dict[str, str] = {}  # tag_id -> description
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def register_tag(self, tag_id: str, description: str) -> bool:
        """
        Register a new tag
        
        Args:
            tag_id: Tag identifier
            description: Tag description
            
        Returns:
            True if newly registered, False if already exists
        """
        tag_id = tag_id.lower()  # Normalize to lowercase
        
        with self.lock:
            if tag_id in self.registered_tags:
                # Update description if different
                if self.registered_tags[tag_id] != description:
                    self.registered_tags[tag_id] = description
                    self.logger.info(f"Updated description for tag {tag_id}")
                return False
            else:
                self.registered_tags[tag_id] = description
                self.logger.info(f"Registered new tag {tag_id}: {description}")
                return True
    
    def is_registered(self, tag_id: str) -> bool:
        """Check if tag is registered"""
        with self.lock:
            return tag_id.lower() in self.registered_tags
    
    def get_description(self, tag_id: str) -> Optional[str]:
        """Get tag description"""
        with self.lock:
            return self.registered_tags.get(tag_id.lower())
    
    def get_all_registered(self) -> Dict[str, str]:
        """Get all registered tags"""
        with self.lock:
            return self.registered_tags.copy()
    
    def unregister_tag(self, tag_id: str) -> bool:
        """Unregister a tag"""
        tag_id = tag_id.lower()
        with self.lock:
            if tag_id in self.registered_tags:
                del self.registered_tags[tag_id]
                self.logger.info(f"Unregistered tag {tag_id}")
                return True
            return False

# Global instances
tag_registry = TagRegistry()
tag_processor = None
app_start_time = datetime.now()

# FastAPI app
app = FastAPI(
    title="RTLS Tag Management API",
    description="REST API for Real-Time Location System Tag Management",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Initialize the tag processor on startup"""
    global tag_processor
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start tag processor in background
    tag_processor = TagProcessor()
    
    # Start processor in separate thread
    def start_processor():
        tag_processor.start()
    
    processor_thread = threading.Thread(target=start_processor, name="TagProcessorThread")
    processor_thread.daemon = True
    processor_thread.start()
    
    # Give processor time to start
    await asyncio.sleep(1)
    
    logging.getLogger(__name__).info("RTLS API Server started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global tag_processor
    
    if tag_processor:
        tag_processor.stop()
    
    logging.getLogger(__name__).info("RTLS API Server stopped")

# API Endpoints

@app.post("/tags", response_model=Dict[str, Any], status_code=201)
async def register_tag(tag_data: TagRegistration):
    """
    Register a new tag
    
    - **id**: Tag identifier (hexadecimal string)
    - **description**: Human readable description
    """
    try:
        # Validate tag ID format (hexadecimal)
        if not all(c in '0123456789abcdefABCDEF' for c in tag_data.id):
            raise HTTPException(
                status_code=400,
                detail="Tag ID must be a hexadecimal string"
            )
        
        # Register tag
        is_new = tag_registry.register_tag(tag_data.id, tag_data.description)
        
        return {
            "message": "Tag registered successfully" if is_new else "Tag description updated",
            "tag_id": tag_data.id.lower(),
            "description": tag_data.description,
            "is_new": is_new
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/tags", response_model=List[TagStatus])
async def get_all_tags():
    """
    Get all registered tags with their current status
    
    Returns list of all registered tags and their real-time status
    """
    try:
        registered_tags = tag_registry.get_all_registered()
        
        if not registered_tags:
            return []
        
        # Get current states from processor
        if tag_processor:
            all_states = tag_processor.get_all_states()
        else:
            all_states = {}
        
        result = []
        for tag_id, description in registered_tags.items():
            state = all_states.get(tag_id, {})
            
            tag_status = TagStatus(
                id=tag_id,
                description=description,
                last_cnt=state.get('last_cnt'),
                last_seen=state.get('last_seen'),
                is_registered=True,
                total_updates=state.get('total_updates', 0)
            )
            result.append(tag_status)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/tag/{tag_id}", response_model=TagStatus)
async def get_tag_status(tag_id: str):
    """
    Get status of a specific tag
    
    - **tag_id**: The tag identifier to query
    """
    try:
        tag_id = tag_id.lower()
        
        
        # Check if tag is registered
        if not tag_registry.is_registered(tag_id):
            raise HTTPException(
                status_code=404,
                detail=f"Tag {tag_id} is not registered"
            )
        
        description = tag_registry.get_description(tag_id)
        
        # Get current state from processor
        if tag_processor:
            state = tag_processor.get_tag_state_dict(tag_id)
        else:
            state = {}
        
        if not state:
            state = {}
        
        return TagStatus(
            id=tag_id,
            description=description,
            last_cnt=state.get('last_cnt'),
            last_seen=state.get('last_seen'),
            is_registered=True,
            total_updates=state.get('total_updates', 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/tag/{tag_id}")
async def unregister_tag(tag_id: str):
    """
    Unregister a tag
    
    - **tag_id**: The tag identifier to unregister
    """
    try:
        tag_id = tag_id.lower()
        
        if tag_registry.unregister_tag(tag_id):
            return {
                "message": f"Tag {tag_id} unregistered successfully",
                "tag_id": tag_id
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Tag {tag_id} is not registered"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """
    System health check
    
    Returns current system status and statistics
    """
    try:
        current_time = datetime.now()
        uptime = current_time - app_start_time
        
        # Get stats from processor
        stats = {
            'total_processed': 0,
            'total_errors': 0
        }
        
        active_tags = 0
        
        if tag_processor:
            processor_stats = getattr(tag_processor, 'stats', {})
            stats.update(processor_stats)
            
            all_states = tag_processor.get_all_states()
            active_tags = len(all_states)
        
        return HealthStatus(
            status="healthy",
            timestamp=current_time.isoformat(),
            uptime=str(uptime),
            active_tags=active_tags,
            total_processed=stats.get('total_processed', 0),
            total_errors=stats.get('total_errors', 0)
        )
        
    except Exception as e:
        # Return unhealthy status but don't raise exception
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            active_tags=0,
            total_processed=0,
            total_errors=1
        )

# Additional utility endpoints

@app.get("/stats")
async def get_detailed_stats():
    """Get detailed system statistics"""
    try:
        registered_count = len(tag_registry.get_all_registered())
        
        if tag_processor:
            all_states = tag_processor.get_all_states()
            processor_stats = getattr(tag_processor, 'stats', {})
        else:
            all_states = {}
            processor_stats = {}
        
        return {
            "registered_tags": registered_count,
            "active_tags": len(all_states),
            "processor_stats": processor_stats,
            "uptime": str(datetime.now() - app_start_time),
            "tag_details": all_states
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Main execution
def main():
    """Run the API server"""
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()