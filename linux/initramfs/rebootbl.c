/* Reboot straight into lk fastboot: reboot(RESTART2, "bootloader").
 * Needs reboot-mode.ko + syscon-reboot-mode.ko loaded so the "bootloader" reason reaches lk (RS-15). */
#include <linux/reboot.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(void)
{
	sync();
	syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
		LINUX_REBOOT_CMD_RESTART2, "bootloader");
	return 1;
}
