<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/database.php';

$currentPage = basename(
    str_replace(
        '\\',
        '/',
        (string) ($_SERVER['SCRIPT_NAME'] ?? 'index.php')
    )
);

$pageClass = pathinfo($currentPage, PATHINFO_FILENAME);

$isLoggedIn = function_exists('is_logged_in')
    ? is_logged_in()
    : false;

$navItems = [
    [
        'file' => 'index.php',
        'href' => './',
        'label' => '动画档案',
    ],
    [
        'file' => 'collection.php',
        'href' => 'collection.php',
        'label' => '我的收藏',
    ],
    [
        'file' => 'admin.php',
        'href' => 'admin.php',
        'label' => '管理',
    ],
];
?>
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1, viewport-fit=cover"
    >
    <meta name="color-scheme" content="dark">
    <meta name="theme-color" content="#090b14">

    <title><?= h($title ?? 'ChronoShelter') ?></title>

    <link
        rel="stylesheet"
        href="static/css/style.css"
    >
    <link
        rel="stylesheet"
        href="static/css/archive-phase2.css"
    >
    <script
        src="static/js/archive-grid.js"
        defer
    ></script>
</head>

<body class="page page-<?= h($pageClass) ?>">
<div class="site-shell">

<header class="topbar">
    <a class="brand" href="./" aria-label="ChronoShelter 首页">
        <span class="brand-mark" aria-hidden="true">
            <span class="brand-mark-core"></span>
        </span>

        <span class="brand-copy">
            <strong>ChronoShelter</strong>
            <small>Animation Archive</small>
        </span>
    </a>

    <?php if ($isLoggedIn): ?>
        <nav class="site-nav" aria-label="主要导航">
            <?php foreach ($navItems as $navItem): ?>
                <?php
                $isActive =
                    $currentPage === $navItem['file'] ||
                    (
                        $currentPage === '' &&
                        $navItem['file'] === 'index.php'
                    );
                ?>
                <a
                    class="nav-link<?= $isActive ? ' is-active' : '' ?>"
                    href="<?= h($navItem['href']) ?>"
                    <?= $isActive ? 'aria-current="page"' : '' ?>
                >
                    <?= h($navItem['label']) ?>
                </a>
            <?php endforeach; ?>

            <a class="nav-link nav-link-logout" href="logout.php">
                退出
            </a>
        </nav>
    <?php endif; ?>
</header>

<main class="wrap">
