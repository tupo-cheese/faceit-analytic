
        if(!Cookies.get('NotificationSeen')) {
            $('#notifications-icon').addClass('notvisited');
        }
        function showNotification() {
            Cookies.set('NotificationSeen',true, { expires: 365 });
            $('#notifications-icon').removeClass('notvisited');
        }
    