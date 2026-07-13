# notifications-service

envío de notificaciones push a conductores y propietarios. 

No se dispara vía REST, sino consumiendo eventos publicados por booking-service y payment-service a través de RabbitMQ. 

booking.confirmed (publicado por booking-service al confirmarse el pago): push al conductor ("reserva confirmada") y al propietario ("nueva reserva recibida").

booking.reminder (publicado por booking-service mediante un job programado antes del horario reservado): push de recordatorio al conductor.

booking.cancelled (publicado por booking-service): push a conductor y propietario informando la cancelación.

payment.completed (publicado por payment-service): push al propietario confirmando que el pago fue acreditado.
