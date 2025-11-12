// ===== MENÚ LATERAL (SIDEBAR) - CUIDA TU BOLSILLO =====

document.addEventListener('DOMContentLoaded', function() {
    const hamburgerBtn = document.getElementById('sidebar-toggle');
    const sidebarMenu = document.getElementById('sidebar-menu');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    
    // Función para abrir el menú
    function openSidebar() {
        hamburgerBtn.classList.add('active');
        sidebarMenu.classList.add('active');
        sidebarOverlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevenir scroll del body
    }
    
    // Función para cerrar el menú
    let closeSidebar = function() {
        hamburgerBtn.classList.remove('active');
        sidebarMenu.classList.remove('active');
        sidebarOverlay.classList.remove('active');
        document.body.style.overflow = ''; // Restaurar scroll del body
    };
    
    // Toggle del menú al hacer clic en el botón hamburger
    if (hamburgerBtn) {
        hamburgerBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (sidebarMenu.classList.contains('active')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }
    
    // Cerrar al hacer clic en el overlay
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            closeSidebar();
        });
    }
    
    // ===== NAVEGACIÓN ENTRE MENÚS Y SUBMENÚS =====
    
    const menuMain = document.getElementById('sidebar-menu-main');
    const submenuTriggers = document.querySelectorAll('.sidebar-submenu-trigger');
    const submenuBacks = document.querySelectorAll('.sidebar-submenu-back');
    
    // Función para mostrar un submenú
    function showSubmenu(submenuId) {
        const submenu = document.getElementById(`sidebar-submenu-${submenuId}`);
        if (submenu) {
            menuMain.classList.add('hidden');
            submenu.classList.add('active');
        }
    }
    
    // Función para volver al menú principal
    function backToMain() {
        const activeSubmenu = document.querySelector('.sidebar-submenu.active');
        if (activeSubmenu) {
            activeSubmenu.classList.remove('active');
            menuMain.classList.remove('hidden');
        }
    }
    
    // Event listeners para triggers de submenús
    submenuTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const submenuId = trigger.getAttribute('data-submenu');
            showSubmenu(submenuId);
        });
    });
    
    // Event listeners para botones de volver
    submenuBacks.forEach(backBtn => {
        backBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            backToMain();
        });
    });
    
    // Cerrar al hacer clic en un enlace del menú (en móvil)
    const sidebarLinks = document.querySelectorAll('.sidebar-nav-item[href], .sidebar-footer-item');
    sidebarLinks.forEach(link => {
        link.addEventListener('click', function() {
            // Solo cerrar en móvil
            if (window.innerWidth <= 768) {
                closeSidebar();
                // Volver al menú principal cuando se cierra
                setTimeout(backToMain, 300);
            }
        });
    });
    
    // Cerrar con tecla ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebarMenu.classList.contains('active')) {
            const activeSubmenu = document.querySelector('.sidebar-submenu.active');
            if (activeSubmenu) {
                // Si hay un submenú activo, volver al menú principal
                backToMain();
            } else {
                // Si estamos en el menú principal, cerrar el sidebar
                closeSidebar();
            }
        }
    });
    
    // Modificar closeSidebar para que también vuelva al menú principal
    const originalCloseSidebar = closeSidebar;
    closeSidebar = function() {
        originalCloseSidebar();
        setTimeout(backToMain, 300);
    };
    
    // Marcar el item activo según la URL actual
    const currentPath = window.location.pathname;
    sidebarLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.includes(href.split('/').pop())) {
            link.classList.add('active');
        }
    });
    
    // Prevenir que el clic en el sidebar cierre el menú
    if (sidebarMenu) {
        sidebarMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    // ===== TOGGLE DE TEMA OSCURO/CLARO =====
    
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    
    // Función para obtener el tema actual
    function getCurrentTheme() {
        return localStorage.getItem('theme') || 'light';
    }
    
    // Función para aplicar el tema
    function applyTheme(theme) {
        const html = document.documentElement;
        if (theme === 'dark') {
            html.setAttribute('data-theme', 'dark');
            if (themeIcon) themeIcon.className = 'fas fa-sun';
            if (themeText) themeText.textContent = 'Modo Claro';
        } else {
            html.setAttribute('data-theme', 'light');
            if (themeIcon) themeIcon.className = 'fas fa-moon';
            if (themeText) themeText.textContent = 'Modo Oscuro';
        }
        localStorage.setItem('theme', theme);
    }
    
    // Cargar tema guardado al iniciar
    const savedTheme = getCurrentTheme();
    applyTheme(savedTheme);
    
    // Toggle del tema
    if (themeToggle) {
        themeToggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const currentTheme = getCurrentTheme();
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    }
});

