package com.ecommerce.payment.service;

import com.ecommerce.common.event.PaymentSucceededEvent;
import com.ecommerce.common.notification.LocalNotificationService;
import com.ecommerce.common.notification.NotificationChannel;
import com.ecommerce.common.notification.NotificationRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.util.Map;

/**
 * Sends the payment-success notification in reaction to {@link PaymentSucceededEvent}.
 *
 * <p>Runs strictly {@link TransactionPhase#AFTER_COMMIT} — the payment
 * transaction has already committed by the time this listener executes, so a
 * notification failure here can never roll back payment confirmation
 * (design-docs/09 §3: "任一后置动作失败不得导致支付确认失败"; PUB-108).
 *
 * <p>Per design-docs/03 §5, business code must submit notifications through
 * {@link LocalNotificationService} only.
 */
@Component
public class PaymentSucceededNotificationListener {

    private static final Logger log = LoggerFactory.getLogger(PaymentSucceededNotificationListener.class);

    private final LocalNotificationService notificationService;

    public PaymentSucceededNotificationListener(LocalNotificationService notificationService) {
        this.notificationService = notificationService;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onPaymentSucceeded(PaymentSucceededEvent event) {
        log.info("Sending payment-success notification: paymentNo={}", event.getPaymentNo());

        NotificationRequest request = new NotificationRequest();
        request.setBizType("PAYMENT_SUCCESS");
        request.setBizId(event.getPaymentNo());
        // design-docs/15 §2: 支付成功通知走 SMS,不是 EMAIL(EMAIL 只用于注册激活/发票).
        request.setChannel(NotificationChannel.SMS);
        request.setTemplateCode("payment_success");
        request.setVariables(Map.of(
                "paymentNo", event.getPaymentNo(),
                "amount", event.getPaidAmount().toString()
        ));
        request.setIdempotencyKey("pay_notify_" + event.getPaymentNo());
        notificationService.send(request);
    }
}
