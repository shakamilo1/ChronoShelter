<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/auth.php';

require_login();
session_write_close();

require dirname(__DIR__) . '/install_check.php';