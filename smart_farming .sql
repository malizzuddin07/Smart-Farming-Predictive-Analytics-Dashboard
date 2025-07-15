-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jul 15, 2025 at 04:38 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `smart_farming`
--

-- --------------------------------------------------------

--
-- Table structure for table `farmer_task_steps`
--

CREATE TABLE `farmer_task_steps` (
  `id` int(11) NOT NULL,
  `ic` varchar(20) DEFAULT NULL,
  `task_id` varchar(100) DEFAULT NULL,
  `status` enum('soon','in_process','completed','skipped') DEFAULT 'soon',
  `start_date` date DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `remarks` text DEFAULT NULL,
  `detail1` varchar(255) DEFAULT NULL,
  `detail2` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `farmer_task_steps`
--

INSERT INTO `farmer_task_steps` (`id`, `ic`, `task_id`, `status`, `start_date`, `completed_at`, `remarks`, `detail1`, `detail2`, `created_at`) VALUES
(21, '123', 'PRE-PLANTING: Soil suitability check', 'in_process', '2025-05-16', '2025-07-15 22:29:45', '', '', '', '2025-07-15 14:20:30'),
(22, '123', 'Bajak 1: Remove stubble, compost, plow', 'in_process', '2025-06-15', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(23, '123', 'Bajak 2: Repeat plowing, break clumps', 'in_process', '2025-07-05', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(24, '123', 'Place AWD tube (optional)', 'in_process', '2025-07-12', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(25, '123', 'Bajak 3/Badai: Final leveling', 'in_process', '2025-07-13', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(26, '123', 'PLANTING: Certified seeds, apply water (AWD), direct seeding', 'in_process', '2025-07-15', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(27, '123', 'VEGETATIVE: AWD water control', 'soon', '2025-07-16', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(28, '123', 'Fertilization 1: NPK 17:20:10', 'soon', '2025-07-21', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(29, '123', 'Maintain 3–5 cm water, AWD & LCC tool', 'soon', '2025-07-23', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(30, '123', 'Fertilization 2: Urea', 'soon', '2025-08-01', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(31, '123', 'Fertilization 3: Compound + Supplement', 'soon', '2025-08-12', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(32, '123', 'REPRODUCTIVE: Continue AWD', 'soon', '2025-08-29', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(33, '123', 'Panicle formation care', 'soon', '2025-09-05', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(34, '123', 'Fertilization 4: Supplement', 'soon', '2025-09-15', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(35, '123', 'Maintain 5 cm water (flowering)', 'soon', '2025-09-21', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(36, '123', 'GRAIN FILLING: Resume AWD', 'soon', '2025-09-28', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(37, '123', 'Dry field to 0 cm', 'soon', '2025-10-18', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(38, '123', 'HARVEST', 'soon', '2025-11-02', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(39, '123', 'POST-HARVEST: Grain drying & storage', 'soon', '2025-11-13', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30'),
(40, '123', 'End season: Cleanup & data analysis', 'soon', '2025-11-17', NULL, NULL, NULL, NULL, '2025-07-15 14:20:30');

-- --------------------------------------------------------

--
-- Table structure for table `prediction_history`
--

CREATE TABLE `prediction_history` (
  `id` int(11) NOT NULL,
  `ic` varchar(20) DEFAULT NULL,
  `location` varchar(100) DEFAULT NULL,
  `field_size` float DEFAULT NULL,
  `yield_per_hectare` float DEFAULT NULL,
  `total_yield` float DEFAULT NULL,
  `predicted_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `prediction_history`
--

INSERT INTO `prediction_history` (`id`, `ic`, `location`, `field_size`, `yield_per_hectare`, `total_yield`, `predicted_at`) VALUES
(14, '123', 'Changlun', 10, 4.6975, 46.975, '2025-07-15 14:20:30');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `fullname` varchar(100) DEFAULT NULL,
  `ic` varchar(20) DEFAULT NULL,
  `state` varchar(50) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `password` varchar(100) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `fullname`, `ic`, `state`, `phone`, `password`) VALUES
(1, 'Akmal Izzuddin', '123', 'PERAK', '01223', '020825'),
(3, 'Test User', '123456', 'Kedah', '011', '0000');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `farmer_task_steps`
--
ALTER TABLE `farmer_task_steps`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `prediction_history`
--
ALTER TABLE `prediction_history`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `ic` (`ic`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `farmer_task_steps`
--
ALTER TABLE `farmer_task_steps`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=41;

--
-- AUTO_INCREMENT for table `prediction_history`
--
ALTER TABLE `prediction_history`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=15;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
