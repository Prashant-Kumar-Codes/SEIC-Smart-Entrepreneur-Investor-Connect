/**
 * Sidebar Mobile Toggle
 * Handles hamburger menu for mobile/tablet devices
 */

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const closeBtn = document.getElementById('sidebarCloseBtn');
    
    if (!sidebar || !overlay) return;

    // Get hamburger button 
    const hamburgerBtn = document.getElementById('sidebarToggleBtn');

    // Toggle sidebar on hamburger click
    if (hamburgerBtn) {
        hamburgerBtn.addEventListener('click', function(e) {
            e.preventDefault();
            sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
        });
    }

    // Close sidebar on close button click
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
        });
    }

    // Close sidebar on overlay click
    overlay.addEventListener('click', function() {
        sidebar.classList.remove('active');
        overlay.classList.remove('active');
    });

    // Close sidebar when a nav link is clicked
    const navLinks = sidebar.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            // Don't close for external links (like logout with onclick)
            if (this.href && !this.getAttribute('onclick')) {
                sidebar.classList.remove('active');
                overlay.classList.remove('active');
            }
        });
    });

    // Close sidebar on window resize if we go back to desktop
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
        }
    });
});
