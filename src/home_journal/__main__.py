"""Home Journal main module."""

import logging

from .run import main


if __name__ == "__main__":
    logger = logging.getLogger("home_journal")
    logger.propagate = False
    file_handler = logging.FileHandler("hj.log")
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s '%(name)s.%(funcName)s' %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)
    logger.info("Started")
    main()
