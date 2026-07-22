-- TravelMind MVP schema for MySQL 8.x.
-- Relationships use logical foreign keys, so no FOREIGN KEY constraints are created.

CREATE TABLE IF NOT EXISTS trips (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '行程ID',
    owner_id VARCHAR(200) NOT NULL DEFAULT 'anonymous' COMMENT '逻辑用户标识',
    thread_id VARCHAR(200) NULL COMMENT '创建行程的 Agent 会话',
    origin VARCHAR(100) NOT NULL COMMENT '出发地',
    destination VARCHAR(100) NOT NULL COMMENT '目的地',
    start_at DATETIME NULL COMMENT '行程开始时间',
    end_at DATETIME NULL COMMENT '行程结束时间',
    budget DECIMAL(10, 2) NULL COMMENT '行程预算',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT '行程状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    INDEX idx_trips_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程主表';

CREATE TABLE IF NOT EXISTS users (
    id BIGINT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='本地用户表';

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(200) NOT NULL,
    max_walking_distance_m INT NULL,
    preferred_transport JSON NOT NULL,
    dietary_restrictions JSON NOT NULL,
    travels_with_elderly BOOLEAN NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户出行偏好';

CREATE TABLE IF NOT EXISTS harness_tasks (
    task_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(200) NOT NULL,
    thread_id VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    blocked_by JSON NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    result TEXT NULL,
    agent_id VARCHAR(50) NOT NULL DEFAULT 'travel_agent',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id),
    INDEX idx_harness_tasks_user_thread (user_id, thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Harness任务';

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id VARCHAR(200) NOT NULL,
    expires_at DATETIME NOT NULL,
    PRIMARY KEY (event_id),
    INDEX idx_webhook_events_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Webhook幂等记录';

CREATE TABLE IF NOT EXISTS outbox_events (
    id BIGINT NOT NULL AUTO_INCREMENT,
    topic VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    idempotency_key VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    available_at DATETIME NOT NULL,
    last_error TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_outbox_idempotency (idempotency_key),
    INDEX idx_outbox_pending (status, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='可靠外部写入队列';

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trip_id BIGINT NOT NULL,
    user_id VARCHAR(200) NOT NULL,
    thread_id VARCHAR(200) NULL,
    kind VARCHAR(50) NOT NULL,
    run_at DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    result JSON NULL,
    last_error TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_scheduled_trip_kind (trip_id, kind),
    INDEX idx_scheduled_due (status, run_at),
    INDEX idx_scheduled_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='出行自动检查任务';

CREATE TABLE IF NOT EXISTS itinerary_items (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '日程项ID',
    trip_id BIGINT NOT NULL COMMENT '所属行程ID（逻辑外键）',
    day_number INT NOT NULL COMMENT '行程第几天',
    sort_order INT NOT NULL COMMENT '当天排序序号',
    title VARCHAR(200) NOT NULL COMMENT '日程标题',
    location VARCHAR(200) NOT NULL COMMENT '地点',
    start_at DATETIME NULL COMMENT '开始时间',
    end_at DATETIME NULL COMMENT '结束时间',
    estimated_cost DECIMAL(10, 2) NOT NULL DEFAULT 0 COMMENT '预计费用',
    source VARCHAR(100) NULL COMMENT '数据来源',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    INDEX idx_itinerary_items_trip_order (trip_id, day_number, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程日程项表';
