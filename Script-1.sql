-- FIXED SQL: Forces Identical Collation and Attributes
SET FOREIGN_KEY_CHECKS=0;
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+08:00";

-- 1. USERS
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `fullname` varchar(100) DEFAULT NULL,
  `ic` varchar(20) NOT NULL, -- Changed to NOT NULL to match planting_sessions
  `state` varchar(50) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `password` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ic` (`ic`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `users` (`id`, `fullname`, `ic`, `state`, `phone`, `password`) VALUES
(1, 'Akmal Izzuddin', '123', 'PERAK', '01223', '12345687');

-- 2. WORKFLOW TEMPLATES
DROP TABLE IF EXISTS `workflow_templates`;
CREATE TABLE `workflow_templates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `harvest_day_offset` int DEFAULT 110,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `workflow_templates` (`id`, `name`, `description`, `harvest_day_offset`) VALUES
(1, 'Standard Paddy (125 Days)', 'A standard 125-day planting schedule.', 110);

-- 3. PLANTING SESSIONS
DROP TABLE IF EXISTS `planting_sessions`;
CREATE TABLE `planting_sessions` (
  `session_id` int NOT NULL AUTO_INCREMENT,
  `user_ic` varchar(20) NOT NULL, -- Matches users.ic exactly now
  `session_name` varchar(255) NOT NULL,
  `location` varchar(255) NOT NULL,
  `latitude` float DEFAULT NULL,
  `longitude` float DEFAULT NULL,
  `field_size` float NOT NULL,
  `planting_date` date NOT NULL,
  `expected_harvest_date` date DEFAULT NULL,
  `predicted_yield_per_ha` float DEFAULT NULL,
  `predicted_total_yield` float DEFAULT NULL,
  `template_id_used` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`session_id`),
  KEY `user_ic` (`user_ic`),
  CONSTRAINT `fk_user_ic` FOREIGN KEY (`user_ic`) REFERENCES `users` (`ic`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 4. FARMER TASK STEPS
DROP TABLE IF EXISTS `farmer_task_steps`;
CREATE TABLE `farmer_task_steps` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_id` int NOT NULL,
  `user_ic` varchar(20) NOT NULL,
  `task_name` varchar(255) NOT NULL,
  `status` enum('soon','in_process','completed','skipped') NOT NULL DEFAULT 'soon',
  `start_date` date DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `remarks` text DEFAULT NULL,
  `detail1` varchar(255) DEFAULT NULL,
  `detail2` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `session_id_user_ic` (`session_id`,`user_ic`),
  CONSTRAINT `fk_session_id_task` FOREIGN KEY (`session_id`) REFERENCES `planting_sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 5. PREDICTION HISTORY
DROP TABLE IF EXISTS `prediction_history`;
CREATE TABLE `prediction_history` (
  `history_id` int NOT NULL AUTO_INCREMENT,
  `session_id` int NOT NULL,
  `TMIN_All` float DEFAULT NULL,
  `TMAX_All` float DEFAULT NULL,
  `RAIN1` float DEFAULT NULL,
  `NDVI_BOHOR` float DEFAULT NULL,
  `TotalSRAD` float DEFAULT NULL,
  `SOIL_pH` float DEFAULT NULL,
  `SOIL_CEC` float DEFAULT NULL,
  `SOIL_OC` float DEFAULT NULL,
  PRIMARY KEY (`history_id`),
  KEY `session_id` (`session_id`),
  CONSTRAINT `fk_session_id_pred` FOREIGN KEY (`session_id`) REFERENCES `planting_sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 6. WORKFLOW TEMPLATE STEPS
DROP TABLE IF EXISTS `workflow_template_steps`;
CREATE TABLE `workflow_template_steps` (
  `id` int NOT NULL AUTO_INCREMENT,
  `template_id` int NOT NULL,
  `task_name` varchar(255) NOT NULL,
  `days_offset` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `template_id` (`template_id`),
  CONSTRAINT `fk_template_id` FOREIGN KEY (`template_id`) REFERENCES `workflow_templates` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `workflow_template_steps` (`id`, `template_id`, `task_name`, `days_offset`) VALUES
(1, 1, 'PRE-PLANTING: Soil suitability check', -60),
(2, 1, 'Bajak 1: Remove stubble, compost, plow', -30),
(3, 1, 'Bajak 2: Repeat plowing, break clumps', -10),
(4, 1, 'Place AWD tube (optional)', -3),
(5, 1, 'Bajak 3/Badai: Final leveling', -2),
(6, 1, 'PLANTING: Certified seeds, apply water (AWD), direct seeding', 0),
(7, 1, 'VEGETATIVE: AWD water control', 1),
(8, 1, 'Fertilization 1: NPK 17:20:10', 6),
(9, 1, 'Maintain 3–5 cm water, AWD & LCC tool', 8),
(10, 1, 'Fertilization 2: Urea', 17),
(11, 1, 'Fertilization 3: Compound + Supplement', 28),
(12, 1, 'REPRODUCTIVE: Continue AWD', 45),
(13, 1, 'Panicle formation care', 52),
(14, 1, 'Fertilization 4: Supplement', 62),
(15, 1, 'Maintain 5 cm water (flowering)', 68),
(16, 1, 'GRAIN FILLING: Resume AWD', 75),
(17, 1, 'Dry field to 0 cm', 95),
(18, 1, 'HARVEST', 110),
(19, 1, 'POST-HARVEST: Grain drying & storage', 121),
(20, 1, 'End season: Cleanup & data analysis', 125);

COMMIT;
SET FOREIGN_KEY_CHECKS=1;