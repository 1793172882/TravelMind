-- TravelMind MVP schema for MySQL 8.x.
-- Relationships use logical foreign keys, so no FOREIGN KEY constraints are created.

CREATE TABLE IF NOT EXISTS trips (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '行程ID',
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
